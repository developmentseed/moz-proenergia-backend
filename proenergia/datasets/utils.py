import csv
from os.path import splitext


def get_file_variant(file_path: str, extension: str):
    path, ext = splitext(file_path)
    return f"{path}.{extension}"


def detect_csv_delimiter(file_path, sample_size=1024):
    """
    Use Python's csv.Sniffer to detect delimiter with improved fallback
    """
    with open(file_path, "r", encoding="utf-8") as f:
        sample = f.read(sample_size)

    # Define valid delimiters
    delimiters = [",", ";", "\t", "|"]

    try:
        # Restrict Sniffer to only check valid delimiters
        dialect = csv.Sniffer().sniff(sample, delimiters="".join(delimiters))
        # Verify the detected delimiter is actually valid
        if dialect.delimiter in delimiters:
            return dialect.delimiter
    except csv.Error:
        pass

    # Fallback to custom detection based on first line
    first_line = sample.split("\n")[0] if "\n" in sample else sample
    delimiter_counts = {d: first_line.count(d) for d in delimiters}
    # Return the delimiter with the highest count (likely the header separator)
    return max(delimiter_counts, key=delimiter_counts.get)
