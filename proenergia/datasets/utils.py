import csv
from os.path import splitext
from decimal import Decimal, InvalidOperation
from typing import Dict, Set, Optional, List
import logging

logger = logging.getLogger(__name__)


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


def infer_field_types_from_data(scenario, sample_size: int = 1000) -> Dict[str, str]:
    """
    Infer field types from actual ScenarioData for a given scenario.
    Samples data to determine if fields are numeric or string.

    Args:
        scenario: Scenario instance to analyze
        sample_size: Number of records to sample for type inference

    Returns:
        Dictionary mapping field names to types ('numeric' or 'string')
    """
    from proenergia.datasets.models import ScenarioData

    # Get all potential fields from both filter_fields and summary_fields
    model = scenario.model
    all_fields = set()

    # Add fields from filter_fields
    for field_config in model.filter_fields or []:
        if column := field_config.get("column"):
            all_fields.add(column)

    # Add fields from summary_fields
    for field_config in model.summary_fields or []:
        if column := field_config.get("column"):
            all_fields.add(column)

    if not all_fields:
        logger.warning(f"No fields configured for model {model.name}")
        return {}

    # Initialize field type tracking
    field_types: Dict[str, Set[str]] = {field: set() for field in all_fields}
    field_samples: Dict[str, List] = {field: [] for field in all_fields}

    # Sample data to infer types
    sample_query = ScenarioData.objects.filter(scenario=scenario)[:sample_size]

    for data in sample_query:
        metadata = data.metadata or {}

        for field in all_fields:
            if field in metadata and metadata[field] is not None:
                value = metadata[field]
                field_samples[field].append(value)

                # Determine type of this value
                if isinstance(value, (int, float)):
                    field_types[field].add("numeric")
                elif isinstance(value, str):
                    # Try to parse as number
                    try:
                        Decimal(value)
                        field_types[field].add("numeric")
                    except (ValueError, InvalidOperation, TypeError):
                        field_types[field].add("string")
                else:
                    # Other types (bool, etc.) treated as string
                    field_types[field].add("string")

    # Determine final type for each field
    inferred_types = {}

    for field, types in field_types.items():
        if not types:
            # No data found for this field, default to string
            logger.debug(
                f"Field '{field}' has no data in scenario {scenario.id}, defaulting to string"
            )
            inferred_types[field] = "string"
        elif len(types) == 1:
            # Consistent type
            inferred_types[field] = list(types)[0]
        else:
            # Mixed types - need to decide based on majority
            samples = field_samples[field]
            numeric_count = 0
            string_count = 0

            for sample in samples:
                try:
                    if sample is not None and sample != "":
                        Decimal(str(sample))
                        numeric_count += 1
                except (ValueError, InvalidOperation, TypeError):
                    string_count += 1

            # Use a threshold: if >80% of values are numeric, treat as numeric
            total_samples = numeric_count + string_count
            if total_samples > 0 and (numeric_count / total_samples) >= 0.8:
                logger.info(
                    f"Field '{field}' has mixed types, {numeric_count}/{total_samples} are numeric, using numeric"
                )
                inferred_types[field] = "numeric"
            else:
                logger.info(
                    f"Field '{field}' has mixed types, {string_count}/{total_samples} are non-numeric, using string"
                )
                inferred_types[field] = "string"

    return inferred_types


def sync_scenario_metrics_with_types(scenario):
    """
    Sync metrics for a scenario, inferring and storing field types.
    This combines type inference and metrics sync in one flow.

    Args:
        scenario: Scenario instance to sync

    Returns:
        Dictionary with sync statistics
    """
    from decimal import Decimal, InvalidOperation
    from django.db import transaction
    from proenergia.datasets.models import ScenarioData, ScenarioDataMetrics

    model = scenario.model

    # Step 1: Infer field types from data
    logger.info(f"Inferring field types for scenario {scenario.id}")
    inferred_types = infer_field_types_from_data(scenario)

    if not inferred_types:
        logger.warning(f"No fields to sync for scenario {scenario.id}")
        return {"fields_synced": 0, "metrics_created": 0}

    # Step 2: Update model's metric_field_types
    model.metric_field_types = inferred_types
    model.save(update_fields=["metric_field_types"])
    logger.info(f"Updated metric_field_types for model {model.name}: {inferred_types}")

    # Step 3: Extract fields by type
    numeric_fields = [f for f, t in inferred_types.items() if t == "numeric"]
    string_fields = [f for f, t in inferred_types.items() if t == "string"]

    logger.info(f"Syncing metrics - numeric: {numeric_fields}, string: {string_fields}")

    # Step 4: Clear existing metrics for this scenario
    deleted_count = ScenarioDataMetrics.objects.filter(scenario=scenario).delete()[0]
    logger.info(f"Cleared {deleted_count} existing metrics for scenario {scenario.id}")

    # Step 5: Create new metrics
    metrics_to_create = []
    batch_size = 5000
    created_count = 0

    with transaction.atomic():
        for data in ScenarioData.objects.filter(scenario=scenario).iterator(
            chunk_size=1000
        ):
            # Extract numeric fields
            for field in numeric_fields:
                if field in data.metadata and data.metadata[field] is not None:
                    try:
                        value = str(data.metadata[field])
                        numeric_value = Decimal(value)
                        metrics_to_create.append(
                            ScenarioDataMetrics(
                                scenario=scenario,
                                feature_id=data.feature_id,
                                key=field,
                                numeric_value=numeric_value,
                            )
                        )
                    except (ValueError, InvalidOperation) as e:
                        logger.debug(
                            f"Could not convert {field}={data.metadata[field]} to numeric: {e}"
                        )

            # Extract string fields
            for field in string_fields:
                if field in data.metadata and data.metadata[field] is not None:
                    metrics_to_create.append(
                        ScenarioDataMetrics(
                            scenario=scenario,
                            feature_id=data.feature_id,
                            key=field,
                            string_value=str(data.metadata[field]),
                        )
                    )

            # Bulk insert when batch size is reached
            if len(metrics_to_create) >= batch_size:
                ScenarioDataMetrics.objects.bulk_create(
                    metrics_to_create, ignore_conflicts=True
                )
                created_count += len(metrics_to_create)
                metrics_to_create = []

        # Insert remaining metrics
        if metrics_to_create:
            ScenarioDataMetrics.objects.bulk_create(
                metrics_to_create, ignore_conflicts=True
            )
            created_count += len(metrics_to_create)

    logger.info(f"Created {created_count} metrics for scenario {scenario.id}")

    return {
        "fields_synced": len(inferred_types),
        "metrics_created": created_count,
        "numeric_fields": numeric_fields,
        "string_fields": string_fields,
    }


