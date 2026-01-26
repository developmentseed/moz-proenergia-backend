import json
import subprocess
from os.path import basename, dirname, join, splitext

import geopandas as gpd
import pandas as pd
from celery import shared_task
from django.apps import apps

from proenergia.datasets.utils import detect_csv_delimiter, get_file_variant


def call_tippecanoe(input_path, output_path):
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


@shared_task
def generate_pmtiles(id: int):
    VectorFile = apps.get_model("datasets", "VectorFile")

    vf = VectorFile.objects.get(id=id)
    vf.status = "processing"
    vf.save(update_fields=["status"])

    try:
        to_pmtiles(vf.file.path)
        vf.status = "ready"
        vf.save(update_fields=["status"])
    except subprocess.CalledProcessError as e:
        print(f"Command failed with exit code {e.returncode}")
        print(f"STDOUT: {e.stdout}")
        print(f"STDERR: {e.stderr}")
        vf.status = "error"
        vf.save(update_fields=["status"])
    except Exception as e:
        print(f"Unexpected error: {e}")
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
    columns = [f.get("column") for f in json.loads(filter_fields)] + ["id"]
    vector.merge(model_data[columns], on="id").to_file(
        merged_file_path, driver="FlatGeobuf"
    )
    print(f"Merged file created on {merged_file_path}.")


@shared_task
def generate_scenario_pmtiles(id: int):
    ScenarioFile = apps.get_model("datasets", "ScenarioFile")
    sf = ScenarioFile.objects.get(id=id)
    vf = sf.scenario.vector_dataset.latest_file()
    if not vf:
        print(
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
