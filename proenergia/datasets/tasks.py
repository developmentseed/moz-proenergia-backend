import csv
import json
import logging
import subprocess
import time
from os import remove
from os.path import basename, dirname, join, splitext
from typing import Dict, Iterator, List

import geopandas as gpd
import pandas as pd
from celery import shared_task
from django.apps import apps
from django.db import connection, transaction

from proenergia.datasets.cache_utils import invalidate_scenario_summary_cache
from proenergia.datasets.utils import detect_csv_delimiter, get_file_variant

logger = logging.getLogger(__name__)


def call_tippecanoe(
    input_path: str, output_path: str, min_zoom: int = 5, max_zoom: int | None = None
):
    subprocess.run(
        [
            "tippecanoe",
            f"-Z{min_zoom}",
            f"-z{max_zoom}" if max_zoom else "-zg",
            "-pk",
            "-pf",
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


def join_pmtiles(low_zoom_path: str, high_zoom_path: str, output_path: str):
    subprocess.run(
        ["tile-join", "-o", output_path, low_zoom_path, high_zoom_path, "-f"],
        check=True,
        capture_output=True,
        text=True,
    )


def create_centroid_geom_file(input_file: str, output_file: str):
    """Create a geospatial file with the centroid geometries of the input file."""
    gdf = gpd.read_file(input_file)
    gdf.geometry = gdf.centroid
    gdf.to_file(output_file)


def to_pmtiles(file_path: str):
    dir = dirname(file_path)
    filename, extension = splitext(basename(file_path))
    pmtiles_path = join(dir, f"{filename}.pmtiles")
    fgb_path = join(dir, f"{filename}.fgb")
    subprocess.run(
        [
            "ogr2ogr",
            "-t_srs",
            "EPSG:4326",
            "-skipfailures",
            fgb_path,
            f"/vsizip/{file_path}" if file_path.endswith(".zip") else file_path,
        ],
        check=True,  # Raises CalledProcessError on non-zero exit
        capture_output=True,  # Capture stdout and stderr
        text=True,  # Return strings instead of bytes
    )
    call_tippecanoe(fgb_path, pmtiles_path)


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
        vf.error_message = e.stderr
        vf.status = "error"
        vf.save(update_fields=["status", "error_message"])
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        vf.error_message = e
        vf.status = "error"
        vf.save(update_fields=["status", "error_message"])


def merge_vector_scenario_files(
    vector_file_path: str,
    scenario_file_path: str,
    selected_columns: List[str],
    merged_file_path: str,
):
    """Merge a vector geospatial file and a scenario CSV file using geopandas.
    Add the columns from the CSV based on the filter_fields definition.
    The resulting file will be a FlatGeobuf.
    """
    vector = gpd.read_file(vector_file_path)
    # The FID is stored as the index when reading FlatGeobuf; reset it so
    # "id" becomes a regular column that can be used as a merge key.
    if "id" not in vector.columns:
        vector = vector.reset_index().rename(columns={"index": "id"})
    delimiter = detect_csv_delimiter(scenario_file_path)

    selected_columns = list(set(selected_columns + ["id"]))

    # Read CSV with robust error handling
    try:
        model_data = pd.read_csv(
            scenario_file_path,
            sep=delimiter,
            encoding="utf-8",
            usecols=selected_columns,  # Load only required columns upfront
            on_bad_lines="skip",  # Skip malformed lines instead of failing
            engine="python",  # More flexible parser
        )
    except Exception as e:
        logger.error(f"Failed to read CSV file {scenario_file_path}: {e}")
        raise e

    vector.merge(model_data, on="id").to_file(merged_file_path, driver="FlatGeobuf")
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
        msg = (
            f"There is not a VectorFile associated with the Scenario {sf.scenario.name}"
        )
        logger.error(msg)
        sf.error_message = msg
        sf.status = "error"
        sf.save(update_fields=["status", "error_message"])

    sf.status = "processing"
    sf.save(update_fields=["status"])

    try:
        model = sf.scenario.model
        fgb_path = get_file_variant(sf.file.path, "fgb")
        columns = [i.get("column") for i in model.filter_fields]
        if model.visualization_column and model.visualization_column not in columns:
            columns.append(model.visualization_column)

        merge_vector_scenario_files(
            get_file_variant(vf.file.path, "fgb"),
            sf.file.path,
            columns,
            fgb_path,
        )
        pmtiles_final_path = get_file_variant(sf.file.path, "pmtiles")

        # if low_zoom_as_points is selected, use centroid geometries for low zoom levels
        if sf.low_zoom_as_points:
            low_zoom_file = pmtiles_final_path.replace(".pmtiles", "_low_zoom.pmtiles")
            high_zoom_file = pmtiles_final_path.replace(
                ".pmtiles", "_high_zoom.pmtiles"
            )
            centroid_file = fgb_path.replace(".fgb", "_centroid.fgb")
            create_centroid_geom_file(fgb_path, centroid_file)
            call_tippecanoe(centroid_file, low_zoom_file, min_zoom=5, max_zoom=10)
            call_tippecanoe(fgb_path, high_zoom_file, min_zoom=11, max_zoom=14)
            join_pmtiles(low_zoom_file, high_zoom_file, pmtiles_final_path)
            # delete intermediate files
            remove(centroid_file)
            remove(low_zoom_file)
            remove(high_zoom_file)
        else:
            call_tippecanoe(fgb_path, pmtiles_final_path)

        logger.info(f"Created PMTiles for scenario {sf.id} on {pmtiles_final_path}")

        import_scenario_data_csv(id)
    except Exception as e:
        logger.error(f"Unexpected error during PMTiles generation: {e}")
        sf.error_message = e
        sf.status = "error"
        sf.save(update_fields=["status", "error_message"])


class DataImporter:
    def __init__(self, scenario_file_id: int, chunk_size: int = 5000):
        ScenarioFile = apps.get_model("datasets", "ScenarioFile")
        self.scenario_file = ScenarioFile.objects.get(id=scenario_file_id)
        self.delimiter = detect_csv_delimiter(self.scenario_file.file.path)
        self.ScenarioData = apps.get_model("datasets", "ScenarioData")
        self.chunk_size = chunk_size
        self.total_rows = 0
        self.batch_times = []
        self.imported_ids = []

    @staticmethod
    def convert_value(value: str):
        """Convert string values to appropriate types (int, float, or keep as string)"""
        if not value:
            return value

        # Try to convert to number
        try:
            # Try integer first
            if "." not in value:
                return int(value)
            # Otherwise try float
            return float(value)
        except (ValueError, AttributeError):
            # Keep as string if conversion fails
            return value

    def stream_csv_chunks(self) -> Iterator[List[Dict]]:
        """Stream CSV in chunks to minimize memory usage"""
        with open(self.scenario_file.file.path, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f, delimiter=self.delimiter)
            current_chunk = []

            for i, row in enumerate(reader, 1):
                # Process row: extract ID, rest goes to JSON
                try:
                    external_id = row.pop("id")
                    if not external_id:
                        continue
                except KeyError:
                    continue

                self.imported_ids.append(external_id)

                # Convert numeric strings to appropriate types
                metadata = {
                    key: self.convert_value(value) for key, value in row.items()
                }

                processed_row = {
                    "feature_id": external_id,
                    "scenario_id": self.scenario_file.scenario.id,
                    "metadata": metadata,
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

        # Prepare values for bulk insert
        values_list = []
        params = []

        for obj in objects:
            values_list.append("(%s, %s, %s::jsonb)")
            params.extend(
                [obj["feature_id"], obj["scenario_id"], json.dumps(obj["metadata"])]
            )

        query = f"""
            INSERT INTO {self.ScenarioData._meta.db_table}
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
        deletion = (
            self.ScenarioData.objects.filter(scenario=self.scenario_file.scenario)
            .exclude(feature_id__in=self.imported_ids)
            .delete()
        )
        logger.info(
            f"Deleted {deletion[0]} ScenarioData items during #{self.scenario_file.id} ScenarioFile import process."
        )

        return {
            "total_rows": self.total_rows,
            "total_time": total_time,
            "rows_per_second": self.total_rows / total_time if total_time > 0 else 0,
            "avg_batch_time": avg_batch_time,
        }


def sync_scenario_metrics(scenario):
    """
    Extract configured fields from ScenarioData to ScenarioDataMetrics table
    for fast aggregation queries.
    """
    from proenergia.datasets.utils import sync_scenario_metrics_with_types

    # Use the new utility function that infers types and syncs metrics
    stats = sync_scenario_metrics_with_types(scenario)

    logger.info(
        f"Metrics sync completed for scenario {scenario.id}: "
        f"{stats['fields_synced']} fields, {stats['metrics_created']} metrics created"
    )


def import_scenario_data_csv(scenario_file_id: int):
    ScenarioFile = apps.get_model("datasets", "ScenarioFile")
    importer = DataImporter(scenario_file_id)

    stats = importer.import_csv()
    logger.info(
        f"ScenarioFile #{scenario_file_id} imported successfully. Rows count: {stats.get('total_rows')}, in {stats.get('total_time')}s"
    )

    # Sync metrics after successful import
    sf = ScenarioFile.objects.get(id=scenario_file_id)
    try:
        sync_scenario_metrics(sf.scenario)

        sf.status = "ready"
        sf.save(update_fields=["status"])
        logger.info(f"Metrics synced successfully for scenario {sf.scenario.id}")
    except Exception as e:
        logger.error(f"Failed to sync metrics for scenario: {e}")
        sf.status = "error"
        sf.error_message = e
        sf.save(update_fields=["status", "error_message"])
        return

    try:
        invalidate_scenario_summary_cache(sf.scenario.id)
    except Exception as e:
        logger.warning(f"Cache invalidation failed for scenario {sf.scenario.id}: {e}")


@shared_task
def delete_item(model_name: str, id: int):
    M = apps.get_model("datasets", model_name)
    M.objects.get(id=id).delete()
