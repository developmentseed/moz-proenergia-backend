"""
SQL query builder for efficient summary computations.

This module constructs optimized SQL queries for aggregating field data
with various combinations of filters and grouping. Raw SQL is used instead
of Django ORM to achieve better performance for complex aggregations.
"""

from typing import List, Tuple, Dict, Optional, Any
from django.db import connection


class SummaryQueryBuilder:
    """
    Builds and executes optimized SQL queries for field summaries.

    Why use raw SQL instead of Django ORM?
    1. Django ORM creates O(n) queries for group_by (one per distinct value)
    2. Multiple filters create deeply nested EXISTS subqueries
    3. Raw SQL with JOINs provides consistent O(1) query complexity

    All queries use parameterized placeholders to prevent SQL injection.
    """

    def build_filtered_query(
        self,
        scenario_id: int,
        field: str,
        field_type: str,
        filter_sql: str,
        filter_params: List,
    ) -> Tuple[str, List]:
        """
        Build SQL for filtered aggregation without grouping.

        This replaces the Django ORM approach that used EXISTS subqueries,
        providing better performance with direct JOINs.

        Args:
            scenario_id: The scenario to aggregate
            field: The field to aggregate
            field_type: 'numeric' or 'string'
            filter_sql: SQL JOIN clauses for filters (from FilterParser)
            filter_params: Parameters for filter JOINs

        Returns:
            Tuple of (SQL query, parameters)
        """
        if field_type == "numeric":
            sql = f"""
            SELECT 
                COUNT(m.numeric_value) as count,
                MIN(m.numeric_value) as min_val,
                MAX(m.numeric_value) as max_val,
                SUM(m.numeric_value) as sum_val
            FROM datasets_scenariodatametrics m
            {filter_sql}
            WHERE m.scenario_id = %s 
                AND m.key = %s
            """
            params = filter_params + [scenario_id, field]
        else:
            # For string fields, we need value distribution
            sql = f"""
            SELECT 
                m.string_value,
                COUNT(*) as count
            FROM datasets_scenariodatametrics m
            {filter_sql}
            WHERE m.scenario_id = %s 
                AND m.key = %s
                AND m.string_value IS NOT NULL
            GROUP BY m.string_value
            ORDER BY m.string_value
            """
            params = filter_params + [scenario_id, field]

        return sql, params

    def build_single_group_query(
        self,
        scenario_id: int,
        field: str,
        field_type: str,
        group_field: str,
        filter_sql: str = "",
        filter_params: List = None,
    ) -> Tuple[str, List]:
        """
        Build SQL for single field grouping.

        This replaces the Django ORM approach that made O(n) queries
        (one per group value) with a single efficient GROUP BY query.

        Args:
            scenario_id: The scenario to aggregate
            field: The field to aggregate
            field_type: 'numeric' or 'string'
            group_field: The field to group by
            filter_sql: Optional SQL JOIN clauses for filters
            filter_params: Optional parameters for filters

        Returns:
            Tuple of (SQL query, parameters)
        """
        if filter_params is None:
            filter_params = []

        if field_type == "numeric":
            # Aggregate numeric values grouped by another field
            sql = f"""
            SELECT 
                g.string_value as group_value,
                COUNT(m.numeric_value) as count,
                MIN(m.numeric_value) as min_val,
                MAX(m.numeric_value) as max_val,
                SUM(m.numeric_value) as sum_val
            FROM datasets_scenariodatametrics m
            INNER JOIN datasets_scenariodatametrics g 
                ON m.feature_id = g.feature_id 
                AND g.scenario_id = %s 
                AND g.key = %s
            {filter_sql}
            WHERE m.scenario_id = %s 
                AND m.key = %s
            GROUP BY g.string_value
            ORDER BY g.string_value
            """
            params = [scenario_id, group_field] + filter_params + [scenario_id, field]
        else:
            # For string fields, we need value distribution per group
            sql = f"""
            SELECT 
                g.string_value as group_value,
                m.string_value as value,
                COUNT(*) as count
            FROM datasets_scenariodatametrics m
            INNER JOIN datasets_scenariodatametrics g 
                ON m.feature_id = g.feature_id 
                AND g.scenario_id = %s 
                AND g.key = %s
            {filter_sql}
            WHERE m.scenario_id = %s 
                AND m.key = %s
                AND m.string_value IS NOT NULL
            GROUP BY g.string_value, m.string_value
            ORDER BY g.string_value, m.string_value
            """
            params = [scenario_id, group_field] + filter_params + [scenario_id, field]

        return sql, params

    def build_multi_group_query(
        self,
        scenario_id: int,
        field: str,
        field_type: str,
        group_fields: List[str],
        filter_sql: str = "",
        filter_params: List = None,
    ) -> Tuple[str, List]:
        """
        Build SQL for multiple field grouping (nested groups).

        This enables hierarchical grouping by multiple fields in a single query,
        avoiding the need for multiple database round-trips.

        Example result structure:
        - group1_value: "Central"
          - group2_value: "SHS"
            - aggregated metrics

        Args:
            scenario_id: The scenario to aggregate
            field: The field to aggregate
            field_type: 'numeric' or 'string'
            group_fields: List of fields to group by (max 2)
            filter_sql: Optional SQL JOIN clauses for filters
            filter_params: Optional parameters for filters

        Returns:
            Tuple of (SQL query, parameters)

        Raises:
            ValueError: If more than 2 group fields provided
        """
        if filter_params is None:
            filter_params = []

        if len(group_fields) > 2:
            raise ValueError("Maximum of 2 group_by fields supported")
        elif len(group_fields) == 1:
            # Delegate to single group query
            return self.build_single_group_query(
                scenario_id,
                field,
                field_type,
                group_fields[0],
                filter_sql,
                filter_params,
            )

        field1, field2 = group_fields

        if field_type == "numeric":
            # Aggregate numeric values with nested grouping
            sql = f"""
            SELECT 
                g1.string_value as group1_value,
                g2.string_value as group2_value,
                COUNT(m.numeric_value) as count,
                MIN(m.numeric_value) as min_val,
                MAX(m.numeric_value) as max_val,
                SUM(m.numeric_value) as sum_val
            FROM datasets_scenariodatametrics m
            INNER JOIN datasets_scenariodatametrics g1 
                ON m.feature_id = g1.feature_id 
                AND g1.scenario_id = %s 
                AND g1.key = %s
            INNER JOIN datasets_scenariodatametrics g2 
                ON m.feature_id = g2.feature_id 
                AND g2.scenario_id = %s 
                AND g2.key = %s
            {filter_sql}
            WHERE m.scenario_id = %s 
                AND m.key = %s
            GROUP BY g1.string_value, g2.string_value
            ORDER BY g1.string_value, g2.string_value
            """
            params = (
                [scenario_id, field1, scenario_id, field2]
                + filter_params
                + [scenario_id, field]
            )
        else:
            # String field value distribution with nested grouping
            sql = f"""
            SELECT 
                g1.string_value as group1_value,
                g2.string_value as group2_value,
                m.string_value as value,
                COUNT(*) as count
            FROM datasets_scenariodatametrics m
            INNER JOIN datasets_scenariodatametrics g1 
                ON m.feature_id = g1.feature_id 
                AND g1.scenario_id = %s 
                AND g1.key = %s
            INNER JOIN datasets_scenariodatametrics g2 
                ON m.feature_id = g2.feature_id 
                AND g2.scenario_id = %s 
                AND g2.key = %s
            {filter_sql}
            WHERE m.scenario_id = %s 
                AND m.key = %s
                AND m.string_value IS NOT NULL
            GROUP BY g1.string_value, g2.string_value, m.string_value
            ORDER BY g1.string_value, g2.string_value, m.string_value
            """
            params = (
                [scenario_id, field1, scenario_id, field2]
                + filter_params
                + [scenario_id, field]
            )

        return sql, params

    def execute_query(self, sql: str, params: List) -> List[Dict[str, Any]]:
        """
        Execute SQL query and return results as list of dictionaries.

        Args:
            sql: The SQL query to execute
            params: Query parameters (properly escaped by database driver)

        Returns:
            List of dictionaries with column names as keys
        """
        with connection.cursor() as cursor:
            cursor.execute(sql, params)
            columns = [col[0] for col in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]
