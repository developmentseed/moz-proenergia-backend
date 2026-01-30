import csv
import json
import logging
import subprocess
import time
from os.path import basename, dirname, join, splitext
from typing import Dict, Iterator, List

import geopandas as gpd
import pandas as pd
from celery import shared_task
from django.apps import apps
from django.db import connection, transaction

from proenergia.datasets.utils import detect_csv_delimiter, get_file_variant

logger = logging.getLogger(__name__)


def call_tippecanoe(input_path: str, output_path: str):
    subprocess.run(
        [
            "tippecanoe",
            "-Z5",
            "-z14",
            "-zg",
            "--projection=EPSG:4326",
            "-o",
            output_path,
            "-l",
            "data",
            input_path,
            "--force",
        ],
        check=True,
        capture_output=True,
        text=True,
    )


def to_pmtiles(file_path: str):
    dir = dirname(file_path)
    filename, extension = splitext(basename(file_path))
    pmtiles_path = join(dir, f"{filename}.pmtiles")
    fgb_path = None
    if extension.lower() not in ["json", "geojson"]:
        fgb_path = join(dir, f"{filename}.fgb")
        subprocess.run(
            [
                "ogr2ogr",
                "-t_srs",
                "EPSG:4326",
                fgb_path,
                f"/vsizip/{file_path}" if file_path.endswith(".zip") else file_path,
            ],
            check=True,  # Raises CalledProcessError on non-zero exit
            capture_output=True,  # Capture stdout and stderr
            text=True,  # Return strings instead of bytes
        )
    call_tippecanoe(fgb_path or file_path, pmtiles_path)


@shared_task(bind=True, max_retries=5, default_retry_delay=2)
def generate_pmtiles(self, id: int):
    VectorFile = apps.get_model("datasets", "VectorFile")

    try:
        vf = VectorFile.objects.get(id=id)
    except VectorFile.DoesNotExist as e:
        # Retry with exponential backoff
        logger.warning(
            f"VectorFile {id} not found, retrying... (attempt {self.request.retries + 1})"
        )
        raise self.retry(exc=e, countdown=2**self.request.retries)

    vf.status = "processing"
    vf.save(update_fields=["status"])

    try:
        to_pmtiles(vf.file.path)
        vf.status = "ready"
        vf.save(update_fields=["status"])
    except subprocess.CalledProcessError as e:
        logger.error(f"Command failed with exit code {e.returncode}")
        logger.error(f"STDOUT: {e.stdout}")
        logger.error(f"STDERR: {e.stderr}")
        vf.status = "error"
        vf.save(update_fields=["status"])
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        vf.status = "error"
        vf.save(update_fields=["status"])


def merge_vector_scenario_files(
    vector_file_path: str, scenario_file_path: str, filter_fields, merged_file_path: str
):
    """Merge a vector geospatial file and a scenario CSV file using geopandas.
    Add the columns from the CSV based on the filter_fields definition.
    The resulting file will be a FlatGeobuf.
    """
    vector = gpd.read_file(vector_file_path)
    delimiter = detect_csv_delimiter(scenario_file_path)
    model_data = pd.read_csv(scenario_file_path, sep=delimiter)
    columns = [f.get("column") for f in filter_fields] + ["id"]
    vector.merge(model_data[columns], on="id").to_file(
        merged_file_path, driver="FlatGeobuf"
    )
    logger.info(f"Merged file created on {merged_file_path}.")


@shared_task(bind=True, max_retries=5, default_retry_delay=2)
def generate_scenario_pmtiles(self, id: int):
    ScenarioFile = apps.get_model("datasets", "ScenarioFile")

    try:
        sf = ScenarioFile.objects.get(id=id)
    except ScenarioFile.DoesNotExist as e:
        # Retry with exponential backoff
        logger.warning(
            f"ScenarioFile {id} not found, retrying... (attempt {self.request.retries + 1})"
        )
        raise self.retry(exc=e, countdown=2**self.request.retries)

    vf = sf.scenario.vector_dataset.latest_file()
    if not vf:
        logger.error(
            f"There is not a VectorFile associated with the Scenario {sf.scenario.name}"
        )
        sf.status = "error"
        sf.save(update_fields=["status"])

    sf.status = "processing"
    sf.save(update_fields=["status"])

    try:
        model = sf.scenario.model
        fgb_path = get_file_variant(sf.file.path, "fgb")
        merge_vector_scenario_files(
            get_file_variant(vf.file.path, "fgb"),
            sf.file.path,
            model.filter_fields,
            fgb_path,
        )
        call_tippecanoe(fgb_path, get_file_variant(sf.file.path, "pmtiles"))

        sf.status = "ready"
        sf.save(update_fields=["status"])
    except Exception as e:
        print(f"Unexpected error: {e}")
        sf.status = "error"
        sf.save(update_fields=["status"])


class CSVImporter:
    def __init__(self, scenario_file_id: int, chunk_size: int = 5000):
        ScenarioFile = apps.get_model("datasets", "ScenarioFile")
        self.scenario_file = ScenarioFile.objects.get(id=scenario_file_id)
        self.chunk_size = chunk_size
        self.total_rows = 0
        self.batch_times = []

    def stream_csv_chunks(self) -> Iterator[List[Dict]]:
        """Stream CSV in chunks to minimize memory usage"""
        with open(self.scenario_file.file.path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            current_chunk = []

            for i, row in enumerate(reader, 1):
                # Process row: extract ID, rest goes to JSON
                external_id = row.pop("id")  # Assuming 'id' column exists

                processed_row = {
                    "feature_id": external_id,
                    "scenario_id": self.scenario_file.id,
                    "metadata": row,  # All remaining columns as JSON
                }
                current_chunk.append(processed_row)

                if len(current_chunk) >= self.chunk_size:
                    yield current_chunk
                    current_chunk = []

            if current_chunk:
                yield current_chunk

    def bulk_create_optimized(self, objects: List[Dict]):
        """Most performant bulk insert using raw SQL"""
        if not objects:
            return

        ScenarioData = apps.get_model("datasets", "ScenarioData")
        # Prepare values for bulk insert
        values_list = []
        params = []

        for obj in objects:
            values_list.append("(%s, %s, %s::jsonb)")
            params.extend(
                [obj["feature_id"], obj["scenario_id"], json.dumps(obj["metadata"])]
            )

        query = f"""
            INSERT INTO {ScenarioData._meta.db_table}
            (feature_id, scenario_id, metadata)
            VALUES {",".join(values_list)}
            ON CONFLICT (feature_id, scenario_id) DO UPDATE
            SET metadata = EXCLUDED.metadata
            RETURNING id;
        """

        with connection.cursor() as cursor:
            cursor.execute(query, params)

    def import_csv(self) -> Dict:
        """Main import method with performance tracking"""
        start_time = time.time()

        with transaction.atomic():
            for chunk_num, chunk in enumerate(self.stream_csv_chunks(), 1):
                chunk_start = time.time()

                # Use raw SQL for maximum performance
                self.bulk_create_optimized(chunk)

                chunk_time = time.time() - chunk_start
                self.batch_times.append(chunk_time)
                self.total_rows += len(chunk)

                print(f"Chunk {chunk_num}: {len(chunk)} rows in {chunk_time:.2f}s")

        total_time = time.time() - start_time
        avg_batch_time = (
            sum(self.batch_times) / len(self.batch_times) if self.batch_times else 0
        )

        return {
            "total_rows": self.total_rows,
            "total_time": total_time,
            "rows_per_second": self.total_rows / total_time if total_time > 0 else 0,
            "avg_batch_time": avg_batch_time,
        }
