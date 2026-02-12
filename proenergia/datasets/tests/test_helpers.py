from proenergia.datasets.models import ScenarioDataMetrics


def create_scenario_metrics(scenario, data_dict):
    """
    Helper to create ScenarioDataMetrics for testing
    
    Args:
        scenario: Scenario instance
        data_dict: Dictionary where keys are feature_ids and values are dicts of field data
                  Example: {1: {"cost": 100, "location": "Maputo"}, 2: {...}}
    
    Returns:
        List of created ScenarioDataMetrics instances
    """
    metrics = []
    for feature_id, row_data in data_dict.items():
        for key, value in row_data.items():
            if isinstance(value, (int, float)):
                metric = ScenarioDataMetrics(
                    scenario=scenario,
                    feature_id=feature_id,
                    key=key,
                    numeric_value=value,
                    string_value=None
                )
            else:
                metric = ScenarioDataMetrics(
                    scenario=scenario,
                    feature_id=feature_id,
                    key=key,
                    numeric_value=None,
                    string_value=str(value)
                )
            metrics.append(metric)
    
    ScenarioDataMetrics.objects.bulk_create(metrics)
    return metrics