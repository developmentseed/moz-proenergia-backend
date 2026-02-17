"""
Filter parsing and validation for field summaries.

This module handles parsing of query string filters and generates
SQL JOIN clauses for efficient filtering.
"""

from typing import List, Tuple, Union, Dict, Set


class FilterParser:
    """
    Parses and validates filter parameters for summary queries.

    The parser converts query string filters into structured data and
    generates SQL JOIN clauses for efficient database filtering.
    """

    def __init__(self, field_type_map: Dict[str, str]):
        """
        Initialize the filter parser.

        Args:
            field_type_map: Mapping of field names to their types ('numeric' or 'string')
                           This serves as a whitelist for allowed fields.
        """
        self.field_type_map = field_type_map
        self.numeric_fields = {k for k, v in field_type_map.items() if v == "numeric"}
        self.string_fields = {k for k, v in field_type_map.items() if v == "string"}

    def parse_filter_string(
        self, filter_string: str
    ) -> List[Tuple[str, str, Union[str, List[str]]]]:
        """
        Parse filter string into structured format.

        Supports formats:
        - field=value (equality)
        - field__gte=value (greater than or equal - numeric only)
        - field__lte=value (less than or equal - numeric only)
        - field__in=value1;value2 (multiple values - string only)

        Args:
            filter_string: Comma-separated filter expressions

        Returns:
            List of (field_name, operator, value) tuples

        Raises:
            ValueError: If filter format is invalid or field is not whitelisted
        """
        if not filter_string:
            return []

        filters = []
        for part in filter_string.split(","):
            if "=" not in part:
                continue

            key_op, value = part.split("=", 1)
            key_op = key_op.strip()
            value = value.strip()

            # Parse operator from field name
            if "__" in key_op:
                field_name, operator = key_op.rsplit("__", 1)
                if operator == "min":
                    operator = "gte"  # Convert min to gte
                elif operator == "max":
                    operator = "lte"  # Convert max to lte
                elif operator not in ["gte", "lte", "in"]:
                    raise ValueError(
                        f"Unsupported operator '{operator}' for field '{field_name}'"
                    )
            else:
                field_name = key_op
                operator = None  # Default to equality

            # Validate field is whitelisted
            if field_name not in self.field_type_map:
                raise ValueError(
                    f"Field '{field_name}' is not configured for summaries."
                )

            # Validate operator is appropriate for field type
            self._validate_operator_for_field(field_name, operator)

            # Parse value for 'in' operator
            if operator == "in":
                value = value.split(";")

            filters.append((field_name, operator, value))

        return filters

    def _validate_operator_for_field(self, field_name: str, operator: str):
        """
        Validate that the operator is appropriate for the field type.

        Numeric fields support: equality (None), gte, lte
        String fields support: equality (None), in

        Raises:
            ValueError: If operator is invalid for field type
        """
        if field_name in self.numeric_fields:
            if operator not in [None, "gte", "lte"]:
                raise ValueError(
                    f"Operator '{operator}' is not valid for numeric field '{field_name}'. "
                    "Use 'gte' (>=) or 'lte' (<=) for numeric comparisons."
                )
        elif field_name in self.string_fields:
            if operator not in [None, "in"]:
                raise ValueError(
                    f"Operator '{operator}' is not valid for string field '{field_name}'. "
                    "Use 'in' for multiple values."
                )

    def build_filter_sql(
        self, 
        filters: List[Tuple[str, str, Union[str, List[str]]]],
        group_fields: List[str] = None
    ) -> Tuple[str, List, Dict[str, str]]:
        """
        Build SQL JOIN clauses and parameters for filters.

        This generates INNER JOINs that efficiently filter results by joining
        on the same metrics table with different conditions. Each filter adds
        a JOIN that ensures only features matching ALL conditions are included.
        
        When a filter field matches a group_by field, we can reuse the group JOIN
        and add the filter condition there, avoiding redundant JOINs.

        Args:
            filters: List of parsed filter tuples
            group_fields: Optional list of fields that are being grouped by (will have g1, g2 aliases)

        Returns:
            Tuple of:
            - SQL string with JOIN clauses for filters not in group_fields
            - List of parameters for those JOINs
            - Dict mapping group field names to their filter conditions (to be added to group JOINs)
        """
        if not filters:
            return "", [], {}

        sql_parts = []
        params = []
        group_filter_conditions = {}  # Maps group field name to SQL condition and params
        
        if group_fields is None:
            group_fields = []

        filter_idx = 0  # Track filter index for non-group filters only
        for field_name, operator, value in filters:
            # Check if this field is already being grouped by
            if field_name in group_fields:
                # This field will be JOINed as g1 or g2, so add filter condition there
                group_idx = group_fields.index(field_name) + 1  # g1 or g2
                alias = f"g{group_idx}"
                
                # Build the filter condition to be added to the group JOIN
                condition_sql = ""
                condition_params = []
                
                if field_name in self.numeric_fields:
                    try:
                        numeric_val = float(value)
                        if operator == "gte":
                            condition_sql = f"                AND {alias}.numeric_value >= %s"
                        elif operator == "lte":
                            condition_sql = f"                AND {alias}.numeric_value <= %s"
                        else:  # equality
                            condition_sql = f"                AND {alias}.numeric_value = %s"
                        condition_params = [numeric_val]
                    except (ValueError, TypeError):
                        raise ValueError(
                            f"Invalid numeric value '{value}' for field '{field_name}'"
                        )
                else:
                    # String field conditions
                    if operator == "in":
                        value_list = value if isinstance(value, list) else [value]
                        placeholders = ",".join(["%s"] * len(value_list))
                        condition_sql = f"                AND {alias}.string_value IN ({placeholders})"
                        condition_params = value_list
                    else:  # equality
                        condition_sql = f"                AND {alias}.string_value = %s"
                        condition_params = [value]
                
                group_filter_conditions[field_name] = (condition_sql, condition_params)
            else:
                # Not a group field, create a separate filter JOIN as before
                alias = f"f{filter_idx}"
                filter_idx += 1

                # Build JOIN clause
                sql_parts.append(f"""
            INNER JOIN datasets_scenariodatametrics {alias}
                ON m.feature_id = {alias}.feature_id
                AND {alias}.scenario_id = %s
                AND {alias}.key = %s""")

                # Add scenario_id and field name as parameters
                params.extend([None, field_name])  # scenario_id will be filled by caller

                # Add value condition based on field type and operator
                if field_name in self.numeric_fields:
                    try:
                        numeric_val = float(value)
                        if operator == "gte":
                            sql_parts.append(
                                f"                AND {alias}.numeric_value >= %s"
                            )
                        elif operator == "lte":
                            sql_parts.append(
                                f"                AND {alias}.numeric_value <= %s"
                            )
                        else:  # equality
                            sql_parts.append(
                                f"                AND {alias}.numeric_value = %s"
                            )
                        params.append(numeric_val)
                    except (ValueError, TypeError):
                        raise ValueError(
                            f"Invalid numeric value '{value}' for field '{field_name}'"
                        )
                else:
                    # String field conditions
                    if operator == "in":
                        value_list = value if isinstance(value, list) else [value]
                        placeholders = ",".join(["%s"] * len(value_list))
                        sql_parts.append(
                            f"                AND {alias}.string_value IN ({placeholders})"
                        )
                        params.extend(value_list)
                    else:  # equality
                        sql_parts.append(f"                AND {alias}.string_value = %s")
                        params.append(value)

        return "".join(sql_parts), params, group_filter_conditions

    def fill_scenario_ids(self, params: List, scenario_id: int) -> List:
        """
        Replace None placeholders in parameters with actual scenario_id.

        This allows building filter SQL before knowing the scenario_id,
        then filling it in later.

        Args:
            params: List of parameters with None placeholders
            scenario_id: The actual scenario ID to use

        Returns:
            New list with scenario_id filled in
        """
        return [scenario_id if p is None else p for p in params]
