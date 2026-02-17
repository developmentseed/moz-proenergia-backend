"""
Aggregation strategies for field summary computations.

This module provides different aggregation strategies optimized for
various query patterns (simple, filtered, grouped).
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Tuple
from django.db.models import Count, Min, Max, Sum

from proenergia.datasets.models import ScenarioDataMetrics
from .filters import FilterParser
from .query_builder import SummaryQueryBuilder


class BaseAggregator(ABC):
    """Base class for field aggregation strategies."""

    @abstractmethod
    def compute_summary(
        self, scenario_id: int, field: str, field_type: str, **kwargs
    ) -> Dict[str, Any]:
        """
        Compute summary statistics for a field.

        Args:
            scenario_id: The scenario to aggregate
            field: The field to aggregate
            field_type: 'numeric' or 'string'
            **kwargs: Additional strategy-specific parameters

        Returns:
            Dictionary with aggregated results
        """
        pass


class SimpleAggregator(BaseAggregator):
    """
    Aggregator for simple queries without filters or grouping.

    Uses Django ORM since these queries are already efficient.
    """

    def compute_summary(
        self, scenario_id: int, field: str, field_type: str, **kwargs
    ) -> Dict[str, Any]:
        """
        Compute simple aggregation using Django ORM.

        This is efficient for simple queries without the complexity
        of filters or grouping.
        """
        metrics_query = ScenarioDataMetrics.objects.filter(
            scenario_id=scenario_id, key=field
        )

        if not metrics_query.exists():
            return {"count": 0}

        if field_type == "numeric":
            # Use Django's aggregation functions
            aggregates = metrics_query.aggregate(
                max_val=Max("numeric_value"),
                min_val=Min("numeric_value"),
                sum_val=Sum("numeric_value"),
                count=Count("numeric_value"),
            )
            return {
                "type": "numeric",
                "count": aggregates["count"] or 0,
                "min": (
                    float(aggregates["min_val"])
                    if aggregates["min_val"] is not None
                    else None
                ),
                "max": (
                    float(aggregates["max_val"])
                    if aggregates["max_val"] is not None
                    else None
                ),
                "sum": (
                    float(aggregates["sum_val"])
                    if aggregates["sum_val"] is not None
                    else None
                ),
            }
        else:
            # Get value distribution for string fields
            values = (
                metrics_query.values("string_value")
                .annotate(count=Count("id"))
                .order_by("string_value")
            )

            return {
                "type": "string",
                "count": sum(v["count"] for v in values),
                "values": {
                    v["string_value"]: v["count"]
                    for v in values
                    if v["string_value"] is not None
                },
            }


class FilteredAggregator(BaseAggregator):
    """
    Aggregator for queries with filters but no grouping.

    Uses raw SQL with JOINs for better performance than nested subqueries.
    """

    def __init__(self):
        self.query_builder = SummaryQueryBuilder()

    def compute_summary(
        self,
        scenario_id: int,
        field: str,
        field_type: str,
        filter_parser: FilterParser,
        filter_string: str,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Compute filtered aggregation using optimized SQL.

        Replaces the Django ORM approach that used EXISTS subqueries
        with direct JOINs for better performance.
        """
        # Parse filters
        filters = filter_parser.parse_filter_string(filter_string)

        # Build filter SQL
        filter_sql, filter_params = filter_parser.build_filter_sql(filters)

        # Fill in scenario IDs
        filter_params = filter_parser.fill_scenario_ids(filter_params, scenario_id)

        # Build and execute query
        sql, params = self.query_builder.build_filtered_query(
            scenario_id, field, field_type, filter_sql, filter_params
        )
        results = self.query_builder.execute_query(sql, params)

        if field_type == "numeric":
            # Process numeric aggregation results
            if not results:
                return {"count": 0}

            row = results[0]
            return {
                "type": "numeric",
                "count": row["count"] or 0,
                "min": float(row["min_val"]) if row["min_val"] is not None else None,
                "max": float(row["max_val"]) if row["max_val"] is not None else None,
                "sum": float(row["sum_val"]) if row["sum_val"] is not None else None,
            }
        else:
            # Process string value distribution
            if not results:
                return {"type": "string", "count": 0, "values": {}}

            total_count = sum(row["count"] for row in results)
            values = {row["string_value"]: row["count"] for row in results}

            return {
                "type": "string",
                "count": total_count,
                "values": values,
            }


class SingleGroupAggregator(BaseAggregator):
    """
    Aggregator for queries with single field grouping.

    Uses raw SQL to avoid O(n) queries that Django ORM would generate.
    """

    def __init__(self):
        self.query_builder = SummaryQueryBuilder()

    def compute_summary(
        self,
        scenario_id: int,
        field: str,
        field_type: str,
        group_field: str,
        all_group_values: List[str],
        filter_parser: Optional[FilterParser] = None,
        filter_string: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Compute grouped aggregation using single SQL query.

        Replaces the Django ORM approach that made one query per group value
        with a single GROUP BY query.
        """
        # Build filter SQL if filters provided
        filter_sql = ""
        filter_params = []
        if filter_parser and filter_string:
            filters = filter_parser.parse_filter_string(filter_string)
            filter_sql, filter_params = filter_parser.build_filter_sql(filters)
            filter_params = filter_parser.fill_scenario_ids(filter_params, scenario_id)

        # Build and execute query
        sql, params = self.query_builder.build_single_group_query(
            scenario_id, field, field_type, group_field, filter_sql, filter_params
        )
        results = self.query_builder.execute_query(sql, params)

        # Process results into grouped structure
        grouped = {}

        if field_type == "numeric":
            # Process numeric results
            for row in results:
                group_value = row["group_value"]
                grouped[group_value] = {
                    "count": row["count"] or 0,
                    "min": (
                        float(row["min_val"]) if row["min_val"] is not None else None
                    ),
                    "max": (
                        float(row["max_val"]) if row["max_val"] is not None else None
                    ),
                    "sum": (
                        float(row["sum_val"]) if row["sum_val"] is not None else None
                    ),
                }

            # Fill in empty groups
            for value in all_group_values:
                if value not in grouped:
                    grouped[value] = {"count": 0, "min": None, "max": None, "sum": None}
        else:
            # Process string value distribution per group
            for row in results:
                group_value = row["group_value"]
                str_value = row["value"]
                count = row["count"]

                if group_value not in grouped:
                    grouped[group_value] = {"count": 0, "values": {}}

                grouped[group_value]["values"][str_value] = count
                grouped[group_value]["count"] += count

            # Fill in empty groups
            for value in all_group_values:
                if value not in grouped:
                    grouped[value] = {"count": 0, "values": {}}

        # Return overall summary with grouped data
        overall = self._compute_overall(
            scenario_id, field, field_type, filter_parser, filter_string
        )
        overall["grouped"] = grouped
        return overall

    def _compute_overall(
        self,
        scenario_id: int,
        field: str,
        field_type: str,
        filter_parser: Optional[FilterParser],
        filter_string: Optional[str],
    ) -> Dict[str, Any]:
        """Compute overall summary (without grouping) for the field."""
        if filter_parser and filter_string:
            # Use FilteredAggregator for overall with filters
            aggregator = FilteredAggregator()
            return aggregator.compute_summary(
                scenario_id, field, field_type, filter_parser, filter_string
            )
        else:
            # Use SimpleAggregator for overall without filters
            aggregator = SimpleAggregator()
            return aggregator.compute_summary(scenario_id, field, field_type)


class MultiGroupAggregator(BaseAggregator):
    """
    Aggregator for queries with multiple field grouping (nested groups).

    Uses raw SQL to efficiently compute hierarchical aggregations.
    """

    def __init__(self):
        self.query_builder = SummaryQueryBuilder()

    def compute_summary(
        self,
        scenario_id: int,
        field: str,
        field_type: str,
        group_fields: List[str],
        all_group_values: Dict[str, List[str]],
        filter_parser: Optional[FilterParser] = None,
        filter_string: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Compute nested grouped aggregation using single SQL query.

        Supports up to 2 levels of grouping for hierarchical data analysis.
        """
        # Build filter SQL if filters provided
        filter_sql = ""
        filter_params = []
        if filter_parser and filter_string:
            filters = filter_parser.parse_filter_string(filter_string)
            filter_sql, filter_params = filter_parser.build_filter_sql(filters)
            filter_params = filter_parser.fill_scenario_ids(filter_params, scenario_id)

        # Build and execute query
        sql, params = self.query_builder.build_multi_group_query(
            scenario_id, field, field_type, group_fields, filter_sql, filter_params
        )
        results = self.query_builder.execute_query(sql, params)

        # Process results into nested structure
        grouped = {}

        if len(group_fields) == 1:
            # Single grouping - delegate to SingleGroupAggregator
            aggregator = SingleGroupAggregator()
            return aggregator.compute_summary(
                scenario_id,
                field,
                field_type,
                group_fields[0],
                all_group_values[group_fields[0]],
                filter_parser,
                filter_string,
            )

        # Multi-level grouping
        field1, field2 = group_fields[:2]

        if field_type == "numeric":
            # Process numeric results with nesting
            for row in results:
                g1_val = row["group1_value"]
                g2_val = row["group2_value"]

                if g1_val not in grouped:
                    grouped[g1_val] = {}

                grouped[g1_val][g2_val] = {
                    "count": row["count"] or 0,
                    "min": (
                        float(row["min_val"]) if row["min_val"] is not None else None
                    ),
                    "max": (
                        float(row["max_val"]) if row["max_val"] is not None else None
                    ),
                    "sum": (
                        float(row["sum_val"]) if row["sum_val"] is not None else None
                    ),
                }

            # Fill in empty groups
            for value1 in all_group_values[field1]:
                if value1 not in grouped:
                    grouped[value1] = {}
                for value2 in all_group_values[field2]:
                    if value2 not in grouped[value1]:
                        grouped[value1][value2] = {
                            "count": 0,
                            "min": None,
                            "max": None,
                            "sum": None,
                        }
        else:
            # Process string value distribution with nesting
            for row in results:
                g1_val = row["group1_value"]
                g2_val = row["group2_value"]
                str_val = row["value"]
                count = row["count"]

                if g1_val not in grouped:
                    grouped[g1_val] = {}
                if g2_val not in grouped[g1_val]:
                    grouped[g1_val][g2_val] = {"count": 0, "values": {}}

                grouped[g1_val][g2_val]["values"][str_val] = count
                grouped[g1_val][g2_val]["count"] += count

            # Fill in empty groups
            for value1 in all_group_values[field1]:
                if value1 not in grouped:
                    grouped[value1] = {}
                for value2 in all_group_values[field2]:
                    if value2 not in grouped[value1]:
                        grouped[value1][value2] = {"count": 0, "values": {}}

        # Return overall summary with grouped data
        overall = self._compute_overall(
            scenario_id, field, field_type, filter_parser, filter_string
        )
        overall["grouped"] = grouped
        return overall

    def _compute_overall(
        self,
        scenario_id: int,
        field: str,
        field_type: str,
        filter_parser: Optional[FilterParser],
        filter_string: Optional[str],
    ) -> Dict[str, Any]:
        """Compute overall summary (without grouping) for the field."""
        if filter_parser and filter_string:
            # Use FilteredAggregator for overall with filters
            aggregator = FilteredAggregator()
            return aggregator.compute_summary(
                scenario_id, field, field_type, filter_parser, filter_string
            )
        else:
            # Use SimpleAggregator for overall without filters
            aggregator = SimpleAggregator()
            return aggregator.compute_summary(scenario_id, field, field_type)


def get_aggregator(
    has_filters: bool, group_fields: Optional[List[str]] = None
) -> BaseAggregator:
    """
    Factory function to get the appropriate aggregator strategy.

    Selection logic:
    - No filters, no grouping → SimpleAggregator (Django ORM)
    - Filters, no grouping → FilteredAggregator (Raw SQL)
    - Single grouping → SingleGroupAggregator (Raw SQL)
    - Multiple grouping → MultiGroupAggregator (Raw SQL)

    Args:
        has_filters: Whether filters are applied
        group_fields: List of fields to group by (if any)

    Returns:
        Appropriate aggregator instance
    """
    if group_fields:
        if len(group_fields) == 1:
            return SingleGroupAggregator()
        else:
            return MultiGroupAggregator()
    elif has_filters:
        return FilteredAggregator()
    else:
        return SimpleAggregator()
