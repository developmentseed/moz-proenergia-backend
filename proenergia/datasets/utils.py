import csv
from os.path import splitext


def get_file_variant(file_path: str, extension: str):
    path, ext = splitext(file_path)
    return f"{path}.{extension}"


def detect_csv_delimiter(file_path, sample_size=1024):
    """
    Use Python's csv.Sniffer to detect delimiter
    """
    with open(file_path, "r", encoding="utf-8") as f:
        sample = f.read(sample_size)

    try:
        dialect = csv.Sniffer().sniff(sample)
        return dialect.delimiter
    except csv.Error:
        # Fallback to custom detection
        delimiters = [",", ";", "\t", "|"]
        delimiter_counts = {d: sample.count(d) for d in delimiters}
        return max(delimiter_counts, key=delimiter_counts.get)
