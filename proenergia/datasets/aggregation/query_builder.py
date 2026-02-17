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
        group_filter_conditions: Dict[str, Tuple[str, List]] = None,
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
        if group_filter_conditions is None:
            group_filter_conditions = {}

        if field_type == "numeric":
            # Build group JOIN with optional filter condition
            group_join_sql = f"""
            INNER JOIN datasets_scenariodatametrics g 
                ON m.feature_id = g.feature_id 
                AND g.scenario_id = %s 
                AND g.key = %s"""

            params_list = [scenario_id, group_field]

            # Add filter condition if this group field has one
            if group_field in group_filter_conditions:
                condition_sql, condition_params = group_filter_conditions[group_field]
                group_join_sql += condition_sql
                params_list.extend(condition_params)

            # Aggregate numeric values grouped by another field
            sql = f"""
            SELECT 
                g.string_value as group_value,
                COUNT(m.numeric_value) as count,
                MIN(m.numeric_value) as min_val,
                MAX(m.numeric_value) as max_val,
                SUM(m.numeric_value) as sum_val
            FROM datasets_scenariodatametrics m
            {group_join_sql}
            {filter_sql}
            WHERE m.scenario_id = %s 
                AND m.key = %s
            GROUP BY g.string_value
            ORDER BY g.string_value
            """
            params = params_list + filter_params + [scenario_id, field]
        else:
            # Build group JOIN with optional filter condition
            group_join_sql = f"""
            INNER JOIN datasets_scenariodatametrics g 
                ON m.feature_id = g.feature_id 
                AND g.scenario_id = %s 
                AND g.key = %s"""

            params_list = [scenario_id, group_field]

            # Add filter condition if this group field has one
            if group_field in group_filter_conditions:
                condition_sql, condition_params = group_filter_conditions[group_field]
                group_join_sql += condition_sql
                params_list.extend(condition_params)

            # For string fields, we need value distribution per group
            sql = f"""
            SELECT 
                g.string_value as group_value,
                m.string_value as value,
                COUNT(*) as count
            FROM datasets_scenariodatametrics m
            {group_join_sql}
            {filter_sql}
            WHERE m.scenario_id = %s 
                AND m.key = %s
                AND m.string_value IS NOT NULL
            GROUP BY g.string_value, m.string_value
            ORDER BY g.string_value, m.string_value
            """
            params = params_list + filter_params + [scenario_id, field]

        return sql, params

    def build_multi_group_query(
        self,
        scenario_id: int,
        field: str,
        field_type: str,
        group_fields: List[str],
        filter_sql: str = "",
        filter_params: List = None,
        group_filter_conditions: Dict[str, Tuple[str, List]] = None,
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
        if group_filter_conditions is None:
            group_filter_conditions = {}

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
                group_filter_conditions,
            )

        field1, field2 = group_fields

        if field_type == "numeric":
            # Build first group JOIN with optional filter condition
            group1_join_sql = f"""
            INNER JOIN datasets_scenariodatametrics g1 
                ON m.feature_id = g1.feature_id 
                AND g1.scenario_id = %s 
                AND g1.key = %s"""

            params_list = [scenario_id, field1]

            # Add filter condition if field1 has one
            if field1 in group_filter_conditions:
                condition_sql, condition_params = group_filter_conditions[field1]
                group1_join_sql += condition_sql
                params_list.extend(condition_params)

            # Build second group JOIN with optional filter condition
            group2_join_sql = f"""
            INNER JOIN datasets_scenariodatametrics g2 
                ON m.feature_id = g2.feature_id 
                AND g2.scenario_id = %s 
                AND g2.key = %s"""

            params_list.extend([scenario_id, field2])

            # Add filter condition if field2 has one
            if field2 in group_filter_conditions:
                condition_sql, condition_params = group_filter_conditions[field2]
                group2_join_sql += condition_sql
                params_list.extend(condition_params)

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
            {group1_join_sql}
            {group2_join_sql}
            {filter_sql}
            WHERE m.scenario_id = %s 
                AND m.key = %s
            GROUP BY g1.string_value, g2.string_value
            ORDER BY g1.string_value, g2.string_value
            """
            params = params_list + filter_params + [scenario_id, field]
        else:
            # Build first group JOIN with optional filter condition
            group1_join_sql = f"""
            INNER JOIN datasets_scenariodatametrics g1 
                ON m.feature_id = g1.feature_id 
                AND g1.scenario_id = %s 
                AND g1.key = %s"""

            params_list = [scenario_id, field1]

            # Add filter condition if field1 has one
            if field1 in group_filter_conditions:
                condition_sql, condition_params = group_filter_conditions[field1]
                group1_join_sql += condition_sql
                params_list.extend(condition_params)

            # Build second group JOIN with optional filter condition
            group2_join_sql = f"""
            INNER JOIN datasets_scenariodatametrics g2 
                ON m.feature_id = g2.feature_id 
                AND g2.scenario_id = %s 
                AND g2.key = %s"""

            params_list.extend([scenario_id, field2])

            # Add filter condition if field2 has one
            if field2 in group_filter_conditions:
                condition_sql, condition_params = group_filter_conditions[field2]
                group2_join_sql += condition_sql
                params_list.extend(condition_params)

            # String field value distribution with nested grouping
            sql = f"""
            SELECT 
                g1.string_value as group1_value,
                g2.string_value as group2_value,
                m.string_value as value,
                COUNT(*) as count
            FROM datasets_scenariodatametrics m
            {group1_join_sql}
            {group2_join_sql}
            {filter_sql}
            WHERE m.scenario_id = %s 
                AND m.key = %s
                AND m.string_value IS NOT NULL
            GROUP BY g1.string_value, g2.string_value, m.string_value
            ORDER BY g1.string_value, g2.string_value, m.string_value
            """
            params = params_list + filter_params + [scenario_id, field]

        return sql, params

    def build_multi_field_query(
        self,
        scenario_id: int,
        fields: Dict[str, str],  # field_name -> field_type mapping
        filter_sql: str = "",
        filter_params: List = None,
    ) -> Tuple[str, List]:
        """
        Build SQL for aggregating multiple fields in a single query.

        This method uses conditional aggregation to compute statistics for
        multiple fields in a single table scan, dramatically reducing query count.

        Args:
            scenario_id: The scenario to aggregate
            fields: Dictionary mapping field names to their types ('numeric' or 'string')
            filter_sql: Optional SQL JOIN clauses for filters
            filter_params: Parameters for filter JOINs

        Returns:
            Tuple of (SQL query, parameters)
        """
        if filter_params is None:
            filter_params = []

        # Separate numeric and string fields
        numeric_fields = [f for f, t in fields.items() if t == "numeric"]
        string_fields = [f for f, t in fields.items() if t == "string"]

        # Build SELECT clause with conditional aggregations
        select_parts = []

        # Add numeric field aggregations
        for field in numeric_fields:
            field_safe = field.replace("'", "''")  # Escape field name for SQL
            select_parts.extend(
                [
                    f"COUNT(CASE WHEN m.key = '{field_safe}' THEN m.numeric_value END) as {field}_count",
                    f"MIN(CASE WHEN m.key = '{field_safe}' THEN m.numeric_value END) as {field}_min",
                    f"MAX(CASE WHEN m.key = '{field_safe}' THEN m.numeric_value END) as {field}_max",
                    f"SUM(CASE WHEN m.key = '{field_safe}' THEN m.numeric_value END) as {field}_sum",
                ]
            )

        # For string fields, we need a different approach - get counts
        for field in string_fields:
            field_safe = field.replace("'", "''")
            select_parts.append(
                f"COUNT(CASE WHEN m.key = '{field_safe}' THEN 1 END) as {field}_count"
            )

        select_clause = ",\n                ".join(select_parts)

        # Build the query
        field_list = list(fields.keys())
        field_list_str = "', '".join(f.replace("'", "''") for f in field_list)

        sql = f"""
            SELECT 
                {select_clause}
            FROM datasets_scenariodatametrics m
            {filter_sql}
            WHERE m.scenario_id = %s 
                AND m.key IN ('{field_list_str}')
        """

        params = filter_params + [scenario_id]
        return sql, params

    def build_multi_field_grouped_query(
        self,
        scenario_id: int,
        fields: Dict[str, str],  # field_name -> field_type mapping
        group_fields: List[str],
        filter_sql: str = "",
        filter_params: List = None,
        group_filter_conditions: Dict[str, Tuple[str, List]] = None,
    ) -> Tuple[str, List]:
        """
        Build SQL for aggregating multiple fields with one or two group_by fields in a single query.

        Args:
            scenario_id: The scenario to aggregate
            fields: Dictionary mapping field names to their types
            group_fields: List of fields to group by (1 or 2)
            filter_sql: Optional SQL JOIN clauses for filters (excluding those merged with groups)
            filter_params: Parameters for filter JOINs
            group_filter_conditions: Dict mapping group field names to (condition_sql, params) for filters on group fields

        Returns:
            Tuple of (SQL query, parameters)
        """
        if filter_params is None:
            filter_params = []
        if group_filter_conditions is None:
            group_filter_conditions = {}

        if len(group_fields) > 2:
            raise ValueError("Maximum of 2 group_by fields supported")

        # Separate numeric and string fields
        numeric_fields = [f for f, t in fields.items() if t == "numeric"]

        # Build SELECT clause based on number of group fields
        if len(group_fields) == 1:
            # Single group field
            group_field = group_fields[0]
            select_parts = ["g.string_value as group_value"]

            for field in numeric_fields:
                field_safe = field.replace("'", "''")
                select_parts.extend(
                    [
                        f"COUNT(CASE WHEN m.key = '{field_safe}' THEN m.numeric_value END) as {field}_count",
                        f"MIN(CASE WHEN m.key = '{field_safe}' THEN m.numeric_value END) as {field}_min",
                        f"MAX(CASE WHEN m.key = '{field_safe}' THEN m.numeric_value END) as {field}_max",
                        f"SUM(CASE WHEN m.key = '{field_safe}' THEN m.numeric_value END) as {field}_sum",
                    ]
                )

            select_clause = ",\n                ".join(select_parts)
            field_list_str = "', '".join(f.replace("'", "''") for f in fields.keys())

            # Build group JOIN with optional filter condition
            group_join_sql = f"""
                INNER JOIN datasets_scenariodatametrics g 
                    ON m.feature_id = g.feature_id 
                    AND g.scenario_id = %s 
                    AND g.key = %s"""

            params_list = [scenario_id, group_field]

            # Add filter condition if this group field has one
            if group_field in group_filter_conditions:
                condition_sql, condition_params = group_filter_conditions[group_field]
                group_join_sql += condition_sql
                params_list.extend(condition_params)

            sql = f"""
                SELECT 
                    {select_clause}
                FROM datasets_scenariodatametrics m
                {group_join_sql}
                {filter_sql}
                WHERE m.scenario_id = %s 
                    AND m.key IN ('{field_list_str}')
                GROUP BY g.string_value
                ORDER BY g.string_value
            """

            params = params_list + filter_params + [scenario_id]
        else:
            # Two group fields
            field1, field2 = group_fields
            select_parts = [
                "g1.string_value as group1_value",
                "g2.string_value as group2_value",
            ]

            for field in numeric_fields:
                field_safe = field.replace("'", "''")
                select_parts.extend(
                    [
                        f"COUNT(CASE WHEN m.key = '{field_safe}' THEN m.numeric_value END) as {field}_count",
                        f"MIN(CASE WHEN m.key = '{field_safe}' THEN m.numeric_value END) as {field}_min",
                        f"MAX(CASE WHEN m.key = '{field_safe}' THEN m.numeric_value END) as {field}_max",
                        f"SUM(CASE WHEN m.key = '{field_safe}' THEN m.numeric_value END) as {field}_sum",
                    ]
                )

            select_clause = ",\n                ".join(select_parts)
            field_list_str = "', '".join(f.replace("'", "''") for f in fields.keys())

            # Build first group JOIN with optional filter condition
            group1_join_sql = f"""
                INNER JOIN datasets_scenariodatametrics g1 
                    ON m.feature_id = g1.feature_id 
                    AND g1.scenario_id = %s 
                    AND g1.key = %s"""

            params_list = [scenario_id, field1]

            # Add filter condition if field1 has one
            if field1 in group_filter_conditions:
                condition_sql, condition_params = group_filter_conditions[field1]
                group1_join_sql += condition_sql
                params_list.extend(condition_params)

            # Build second group JOIN with optional filter condition
            group2_join_sql = f"""
                INNER JOIN datasets_scenariodatametrics g2 
                    ON m.feature_id = g2.feature_id 
                    AND g2.scenario_id = %s 
                    AND g2.key = %s"""

            params_list.extend([scenario_id, field2])

            # Add filter condition if field2 has one
            if field2 in group_filter_conditions:
                condition_sql, condition_params = group_filter_conditions[field2]
                group2_join_sql += condition_sql
                params_list.extend(condition_params)

            sql = f"""
                SELECT 
                    {select_clause}
                FROM datasets_scenariodatametrics m
                {group1_join_sql}
                {group2_join_sql}
                {filter_sql}
                WHERE m.scenario_id = %s 
                    AND m.key IN ('{field_list_str}')
                GROUP BY g1.string_value, g2.string_value
                ORDER BY g1.string_value, g2.string_value
            """

            params = params_list + filter_params + [scenario_id]

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
