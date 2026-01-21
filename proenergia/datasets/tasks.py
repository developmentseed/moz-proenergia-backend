import subprocess
from os.path import basename, dirname, join, splitext

from celery import shared_task

from proenergia.datasets.models import VectorFile


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
    subprocess.run(
        [
            "tippecanoe",
            "-Z5",
            "-z14",
            "-zg",
            "--projection=EPSG:4326",
            "-o",
            pmtiles_path,
            "-l",
            "data",
            fgb_path or file_path,
            "--force",
        ],
        check=True,
        capture_output=True,
        text=True,
    )


@shared_task
def generate_pmtiles(vf: VectorFile):
    vf.status = "processing"
    vf.save()
    try:
        to_pmtiles(vf.file.path)
        vf.status = "ready"
        vf.save()
    except subprocess.CalledProcessError as e:
        print(f"Command failed with exit code {e.returncode}")
        print(f"STDOUT: {e.stdout}")
        print(f"STDERR: {e.stderr}")
        vf.status = "error"
        vf.save()
    except Exception as e:
        print(f"Unexpected error: {e}")
        vf.status = "error"
        vf.save()


@shared_task
def convert_pending_vector_files():
    files = VectorFile.objects.filter(status="created")
    generate_pmtiles.map(vf for vf in files)
