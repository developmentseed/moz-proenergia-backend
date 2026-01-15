import subprocess
from os.path import basename, dirname, join, splitext

from celery import map, shared_task

from proenergia.datasets.models import VectorFile


def to_pmtiles(file_path: str):
    dir = dirname(file_path)
    filename, extension = splitext(basename(file_path))
    pmtiles_path = join(dir, f"{filename}.pmtiles")
    subprocess.run(
        [
            "ogr2ogr",
            "-dsco",
            "MINZOOM=4",
            "-dsco",
            "MAXZOOM=15",
            "-f",
            "PMTiles",
            pmtiles_path,
            f"/vsizip/{file_path}" if file_path.endswith(".zip") else file_path,
            "-nln",
            "data",
        ],
        check=True,  # Raises CalledProcessError on non-zero exit
        capture_output=True,  # Capture stdout and stderr
        text=True,  # Return strings instead of bytes
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


@shared_task
def convert_pending_vectorfiles():
    files = VectorFile.objects.filter(status="created")
    map(generate_pmtiles(vf) for vf in files)()
