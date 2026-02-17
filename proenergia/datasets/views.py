from typing import List, Tuple, Union

from django.db.models import (
    Count,
    Exists,
    FloatField,
    Max,
    Min,
    OuterRef,
    QuerySet,
    Sum,
)
from django.db.models.fields.json import KT
from django.db.models.functions import Cast
from django.db.utils import DataError, InternalError, ProgrammingError
from rest_framework import status
from rest_framework.generics import ListAPIView, RetrieveAPIView, get_object_or_404
from rest_framework.permissions import (
    SAFE_METHODS,
    BasePermission,
    IsAuthenticatedOrReadOnly,
)
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from .filters import ScenarioDataFilter, VectorDatasetFilter
from .models import (
    DataModel,
    Scenario,
    ScenarioData,
    ScenarioDataMetrics,
    VectorDataset,
)
from .pagination import StandardResultsSetPagination
from .serializers import (
    DataModelSerializer,
    ScenarioDataSerializer,
    VectorDatasetSerializer,
)


class PublicApprovedDataset(BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.user and request.user.is_superuser:
            return True
        elif (
            request.method in SAFE_METHODS
            and request.user.is_authenticated
            and obj.is_approved
        ):
            return True
        else:
            return request.method in SAFE_METHODS and obj.is_public and obj.is_approved


class VectorDatasetListView(ListAPIView):
    """Lists VectorDatasets that are public and approved. For logged-in superadmin users, it returns all datasets."""

    serializer_class = VectorDatasetSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    pagination_class = StandardResultsSetPagination
    filterset_class = VectorDatasetFilter

    def get_queryset(self):
        queryset = VectorDataset.objects.select_related("created_by", "last_updated_by")
        if self.request.user and self.request.user.is_superuser:
            return queryset
        elif self.request.user.is_authenticated:
            return queryset.filter(is_approved=True)
        else:
            return queryset.filter(is_public=True, is_approved=True)


class VectorDatasetDetailView(RetrieveAPIView):
    """Returns information about a specific VectorDataset."""

    queryset = VectorDataset.objects.all()
    serializer_class = VectorDatasetSerializer
    permission_classes = [PublicApprovedDataset]


class DataModelListView(ListAPIView):
    """Lists all available DataModel entries."""

    queryset = DataModel.objects.prefetch_related("scenarios")
    serializer_class = DataModelSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]


class DataModelDetailView(RetrieveAPIView):
    """Returns information about a specific DataModel."""

    queryset = DataModel.objects.all()
    serializer_class = DataModelSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]


class ScenarioDataDetailView(RetrieveAPIView):
    """Returns information about a specific feature of a Scenario's data results."""

    queryset = ScenarioData.objects.all()
    serializer_class = ScenarioDataSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get_object(self):
        queryset = self.get_queryset()
        filter = {
            "feature_id": self.kwargs.get("pk"),
            "scenario__id": self.kwargs.get("scenario_id"),
        }
        return get_object_or_404(queryset, **filter)


class MultiFieldSummaryView(APIView):
    """
    Compute statistical summaries on multiple scenario fields with filtering and grouping support.

    **URL:** `/api/v1/scenario/{pk}/summaries/`

    ## Parameters
    - **fields** (required): Comma-separated field names (e.g., `Pop2030,Technology2030`)
    - **q** (optional): Filters using `field=value`, `field__min=value`, `field__max=value`, `field__in=val1;val2`
    - **group_by** (optional): Group results by string fields (max 2), comma-separated (e.g., `district,Technology2030`)

    ## Response Structure
    ```json
    {
        "scenario_id": 1,
        "filters_applied": "Admin_1=Maputo",
        "summaries": {
            "Pop2030": {
                "type": "numeric",
                "count": 7354,
                "min": 3.69,
                "max": 3620782.55,
                "sum": 4466719.88,
                "grouped": {  // Only when group_by used
                    "ExistingGrid": {"count": 100, "min": 10, "max": 1000, "sum": 5000}
                }
            },
            "Technology2030": {
                "type": "string",
                "count": 7354,
                "values": {"ExistingGrid": 100, "SHS": 200},
                "grouped": {  // Only when group_by used
                    "Maputo": {"count": 150, "values": {"ExistingGrid": 50, "SHS": 100}}
                }
            }
        },
        "group_by": ["Admin_1"]  // Array of group_by fields (when grouping used)
    }
    ```

    ## Examples

    **Basic usage:**
    ```
    GET /api/v1/scenario/1/summaries/?fields=Pop2030,Technology2030
    ```

    **With filtering and grouping:**
    ```
    GET /api/v1/scenario/1/summaries/?fields=Pop2030&q=Admin_1=Maputo,Pop2030__min=1000&group_by=Technology2030
    ```

    **With multiple group_by fields:**
    ```
    GET /api/v1/scenario/1/summaries/?fields=Pop2030&group_by=district,Technology2030
    ```

    ## Errors
    - `400`: Missing/invalid fields, unsupported operators
    - `404`: No data found for specified fields

    Fields must be configured in DataModel.summary_fields. Use DataModel API to discover available fields.
    """

    # Supported operators for each field type
    NUMERIC_OPERATORS = {"gte", "lte"}
    STRING_OPERATORS = {"in"}

    permission_classes = [IsAuthenticatedOrReadOnly]

    def get(self, request: Request, pk: int) -> Response:
        # 1. Validate scenario exists
        scenario = get_object_or_404(Scenario, id=pk)

        # 2. Parse and validate fields parameter
        fields_param = request.GET.get("fields", "")
        if not fields_param:
            return Response(
                {"error": "The 'fields' parameter is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        requested_fields = [f.strip() for f in fields_param.split(",") if f.strip()]
        if not requested_fields:
            return Response(
                {"error": "No fields specified."}, status=status.HTTP_400_BAD_REQUEST
            )

        # 3. Get configured fields (but don't validate requested fields)
        field_type_map = self._get_field_type_map(scenario.model)

        # 4. Parse and validate group_by parameter
        group_by_fields = []
        group_by_values = {}
        group_by_param = request.GET.get("group_by", "").strip()

        if group_by_param:
            # Parse comma-separated group_by fields
            group_by_fields = [f.strip() for f in group_by_param.split(",") if f.strip()]
            
            # Limit to maximum 2 fields
            if len(group_by_fields) > 2:
                return Response(
                    {"error": "Maximum of 2 group_by fields allowed."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            
            # Validate each group_by field
            for field in group_by_fields:
                # Validate field exists and is a string field
                if field not in field_type_map:
                    return Response(
                        {
                            "error": f"Group by field '{field}' is not configured for summaries."
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                if field_type_map[field] != "string":
                    return Response(
                        {"error": f"Group by field '{field}' must be a string field."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                # Check field has data
                if not ScenarioDataMetrics.objects.filter(
                    scenario=scenario, key=field
                ).exists():
                    return Response(
                        {"error": f"No data found for group by field '{field}'."},
                        status=status.HTTP_404_NOT_FOUND,
                    )

                # Get all possible values for this group_by field
                group_by_values[field] = self._get_all_group_values(scenario, field)

        # 5. Apply filters once if provided
        filter_params = request.GET.get("q", "")
        base_feature_subquery = None

        if filter_params:
            try:
                base_feature_subquery = self._get_filtered_feature_subquery(
                    scenario, filter_params, field_type_map
                )
            except ValueError as e:
                return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        # 6. Compute summaries for each field
        summaries = {}

        for field in requested_fields:
            # Check if field is configured
            if field not in field_type_map:
                # Invalid/unconfigured field - return count=0
                summaries[field] = {"count": 0}
                continue

            # Build query for this field
            metrics_query = ScenarioDataMetrics.objects.filter(
                scenario=scenario, key=field
            )

            # Apply feature_id filter if filters were provided
            if base_feature_subquery is not None:
                metrics_query = metrics_query.filter(
                    feature_id__in=base_feature_subquery
                )

            # Check if any data exists
            if not metrics_query.exists():
                # No data for this field - return count=0
                summaries[field] = {"count": 0}
                continue

            # Compute overall summary
            field_type = field_type_map[field]
            summary = self._compute_field_summary(metrics_query, field_type)

            # Add grouped summaries if group_by is provided
            if group_by_fields and group_by_values:
                summary["grouped"] = self._compute_grouped_summaries(
                    scenario,
                    field,
                    field_type,
                    group_by_fields,
                    group_by_values,
                    filter_params if filter_params else None,
                    field_type_map,
                )

            summaries[field] = summary

        # 7. Return successful response
        response = {
            "scenario_id": pk,
            "filters_applied": filter_params,
            "summaries": summaries,
        }

        if group_by_fields:
            response["group_by"] = group_by_fields

        return Response(response)

    def _get_field_type_map(self, model):
        """Build a mapping of field names to their types from metric_field_types"""
        return model.metric_field_types or {}

    def _get_all_group_values(self, scenario, group_by_field):
        """Get all unique values for the group_by field in the scenario"""
        return list(
            ScenarioDataMetrics.objects.filter(scenario=scenario, key=group_by_field)
            .values_list("string_value", flat=True)
            .distinct()
            .order_by("string_value")
        )

    def _get_filtered_feature_subquery(self, scenario, filter_string, field_type_map):
        """Apply filters and return a subquery for matching feature_ids"""
        # Parse filter string
        filters = self.parse_filter_string(filter_string)

        # Separate numeric and string fields for validation
        numeric_fields = set(k for k, v in field_type_map.items() if v == "numeric")
        string_fields = set(k for k, v in field_type_map.items() if v == "string")

        # Build a base query to get all feature_ids for this scenario
        base_query = (
            ScenarioDataMetrics.objects.filter(scenario=scenario)
            .values_list("feature_id", flat=True)
            .distinct()
        )

        # Apply each filter
        for field_name, operator, value in filters:
            # Validate field is configured
            if field_name not in field_type_map:
                raise ValueError(
                    f"Field '{field_name}' is not configured for summaries."
                )

            # Validate operator is appropriate for field type
            self._validate_field_operator(
                field_name, operator, numeric_fields, string_fields
            )

            # Build EXISTS subquery
            exists_subquery = self._build_exists_subquery(
                scenario.id, field_name, operator, value, numeric_fields
            )

            # Apply filter to narrow down feature_ids
            base_query = base_query.filter(Exists(exists_subquery))

        # Return the subquery (not executed yet)
        return base_query

    def _compute_field_summary(self, metrics_query, field_type):
        """Compute summary statistics for a field based on its type"""
        if field_type == "numeric":
            # Numeric aggregation
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
            # String aggregation
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

    def _compute_grouped_summaries(
        self,
        scenario,
        field,
        field_type,
        group_by_fields,
        all_group_values,
        filter_params,
        field_type_map,
    ):
        """Compute summaries grouped by one or two fields using efficient subqueries"""
        if len(group_by_fields) == 1:
            # For single grouping, keep existing approach for now
            base_feature_subquery = None
            if filter_params:
                base_feature_subquery = self._get_filtered_feature_subquery(
                    scenario, filter_params, field_type_map
                )
            return self._compute_single_level_grouped_summaries(
                scenario,
                field,
                field_type,
                group_by_fields[0],
                all_group_values[group_by_fields[0]],
                base_feature_subquery,
            )
        else:
            # For nested grouping, pass filter params directly to avoid materialization
            return self._compute_nested_grouped_summaries(
                scenario,
                field,
                field_type,
                group_by_fields,
                all_group_values,
                filter_params,
                field_type_map,
            )

    def _compute_single_level_grouped_summaries(
        self,
        scenario,
        field,
        field_type,
        group_by_field,
        group_values,
        base_feature_subquery,
    ):
        """Compute summaries grouped by a single field"""
        grouped = {}

        for group_value in group_values:
            # Build a subquery to get feature_ids for this group value
            # This avoids creating large IN clauses with thousands of IDs
            group_feature_subquery = ScenarioDataMetrics.objects.filter(
                scenario=scenario, key=group_by_field, string_value=group_value
            ).values_list("feature_id", flat=True)

            # If we have base filters applied, intersect with those
            if base_feature_subquery is not None:
                group_feature_subquery = group_feature_subquery.filter(
                    feature_id__in=base_feature_subquery
                )

            # Build query for this field and group using subquery
            group_query = ScenarioDataMetrics.objects.filter(
                scenario=scenario, key=field, feature_id__in=group_feature_subquery
            )

            # Check if this group has any data
            if not group_query.exists():
                # Empty group - return zeros/empty
                if field_type == "numeric":
                    grouped[group_value] = {
                        "count": 0,
                        "min": None,
                        "max": None,
                        "sum": None,
                    }
                else:
                    grouped[group_value] = {"count": 0, "values": {}}
            else:
                # Compute summary for this group
                if field_type == "numeric":
                    aggregates = group_query.aggregate(
                        max_val=Max("numeric_value"),
                        min_val=Min("numeric_value"),
                        sum_val=Sum("numeric_value"),
                        count=Count("numeric_value"),
                    )
                    grouped[group_value] = {
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
                    values = (
                        group_query.values("string_value")
                        .annotate(count=Count("id"))
                        .order_by("string_value")
                    )

                    grouped[group_value] = {
                        "count": sum(v["count"] for v in values),
                        "values": {
                            v["string_value"]: v["count"]
                            for v in values
                            if v["string_value"] is not None
                        },
                    }

        return grouped

    def _compute_nested_grouped_summaries(
        self,
        scenario,
        field,
        field_type,
        group_by_fields,
        all_group_values,
        filter_params,
        field_type_map,
    ):
        """Compute summaries grouped by two fields using optimized SQL"""
        field1, field2 = group_by_fields
        
        # Parse filters if provided
        filters = None
        if filter_params:
            try:
                filters = self.parse_filter_string(filter_params)
            except ValueError:
                # Invalid filter, return empty groups
                return self._create_empty_nested_groups(field1, field2, all_group_values, field_type)
        
        # Execute optimized query based on field type
        if field_type == "numeric":
            results = self._execute_numeric_grouped_query(
                scenario, field, field1, field2, filters, field_type_map
            )
        else:
            results = self._execute_string_grouped_query(
                scenario, field, field1, field2, filters, field_type_map
            )
        
        # Process results into nested structure
        grouped = self._process_nested_results(results, field_type)
        
        # Fill in empty groups
        return self._fill_empty_groups(grouped, all_group_values, field1, field2, field_type)
    
    def _execute_numeric_grouped_query(self, scenario, field, field1, field2, filters, field_type_map):
        """Execute optimized SQL for numeric field grouping with integrated filters"""
        from django.db import connection
        
        # Separate numeric and string fields for filter building
        numeric_fields = set(k for k, v in field_type_map.items() if v == "numeric")
        
        sql = """
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
        """
        params = [scenario.id, field1, scenario.id, field2]
        
        # Add filter JOINs if filters are present
        if filters:
            for idx, (field_name, operator, value) in enumerate(filters):
                alias = f"f{idx}"
                sql += f"""
            INNER JOIN datasets_scenariodatametrics {alias}
                ON m.feature_id = {alias}.feature_id
                AND {alias}.scenario_id = %s
                AND {alias}.key = %s
                """
                params.extend([scenario.id, field_name])
                
                # Add filter conditions based on field type and operator
                if field_name in numeric_fields:
                    try:
                        numeric_val = float(value)
                        if operator == "gte":
                            sql += f" AND {alias}.numeric_value >= %s"
                        elif operator == "lte":
                            sql += f" AND {alias}.numeric_value <= %s"
                        else:
                            sql += f" AND {alias}.numeric_value = %s"
                        params.append(numeric_val)
                    except (ValueError, TypeError):
                        pass  # Skip invalid numeric filters
                else:
                    # String field
                    if operator == "in":
                        value_list = value if isinstance(value, list) else [value]
                        placeholders = ','.join(['%s'] * len(value_list))
                        sql += f" AND {alias}.string_value IN ({placeholders})"
                        params.extend(value_list)
                    else:
                        sql += f" AND {alias}.string_value = %s"
                        params.append(value)
        
        sql += """
            WHERE m.scenario_id = %s 
                AND m.key = %s
            GROUP BY g1.string_value, g2.string_value
        """
        params.extend([scenario.id, field])
        
        with connection.cursor() as cursor:
            cursor.execute(sql, params)
            columns = [col[0] for col in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]
    
    def _execute_string_grouped_query(self, scenario, field, field1, field2, filters, field_type_map):
        """Execute optimized SQL for string field grouping with integrated filters"""
        from django.db import connection
        
        # Separate numeric and string fields for filter building
        numeric_fields = set(k for k, v in field_type_map.items() if v == "numeric")
        
        sql = """
            SELECT 
                g1.string_value as group1_value,
                g2.string_value as group2_value,
                m.string_value as string_value,
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
        """
        params = [scenario.id, field1, scenario.id, field2]
        
        # Add filter JOINs if filters are present
        if filters:
            for idx, (field_name, operator, value) in enumerate(filters):
                alias = f"f{idx}"
                sql += f"""
            INNER JOIN datasets_scenariodatametrics {alias}
                ON m.feature_id = {alias}.feature_id
                AND {alias}.scenario_id = %s
                AND {alias}.key = %s
                """
                params.extend([scenario.id, field_name])
                
                # Add filter conditions based on field type and operator
                if field_name in numeric_fields:
                    try:
                        numeric_val = float(value)
                        if operator == "gte":
                            sql += f" AND {alias}.numeric_value >= %s"
                        elif operator == "lte":
                            sql += f" AND {alias}.numeric_value <= %s"
                        else:
                            sql += f" AND {alias}.numeric_value = %s"
                        params.append(numeric_val)
                    except (ValueError, TypeError):
                        pass  # Skip invalid numeric filters
                else:
                    # String field
                    if operator == "in":
                        value_list = value if isinstance(value, list) else [value]
                        placeholders = ','.join(['%s'] * len(value_list))
                        sql += f" AND {alias}.string_value IN ({placeholders})"
                        params.extend(value_list)
                    else:
                        sql += f" AND {alias}.string_value = %s"
                        params.append(value)
        
        sql += """
            WHERE m.scenario_id = %s 
                AND m.key = %s
            GROUP BY g1.string_value, g2.string_value, m.string_value
            ORDER BY g1.string_value, g2.string_value, m.string_value
        """
        params.extend([scenario.id, field])
        
        with connection.cursor() as cursor:
            cursor.execute(sql, params)
            columns = [col[0] for col in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]
    
    def _process_nested_results(self, results, field_type):
        """Process query results into nested dictionary structure"""
        grouped = {}
        
        if field_type == "numeric":
            for row in results:
                g1_val = row["group1_value"]
                g2_val = row["group2_value"]
                
                if g1_val not in grouped:
                    grouped[g1_val] = {}
                
                grouped[g1_val][g2_val] = {
                    "count": row["count"] or 0,
                    "min": float(row["min_val"]) if row["min_val"] is not None else None,
                    "max": float(row["max_val"]) if row["max_val"] is not None else None,
                    "sum": float(row["sum_val"]) if row["sum_val"] is not None else None,
                }
        else:
            # String field processing
            for row in results:
                g1_val = row["group1_value"]
                g2_val = row["group2_value"]
                str_val = row["string_value"]
                count = row["count"]
                
                if g1_val not in grouped:
                    grouped[g1_val] = {}
                if g2_val not in grouped[g1_val]:
                    grouped[g1_val][g2_val] = {"count": 0, "values": {}}
                
                if str_val is not None:
                    grouped[g1_val][g2_val]["values"][str_val] = count
                    grouped[g1_val][g2_val]["count"] += count
        
        return grouped
    
    def _fill_empty_groups(self, grouped, all_group_values, field1, field2, field_type):
        """Fill in empty groups with zero counts"""
        for value1 in all_group_values[field1]:
            if value1 not in grouped:
                grouped[value1] = {}
            
            for value2 in all_group_values[field2]:
                if value2 not in grouped[value1]:
                    if field_type == "numeric":
                        grouped[value1][value2] = {
                            "count": 0,
                            "min": None,
                            "max": None,
                            "sum": None,
                        }
                    else:
                        grouped[value1][value2] = {"count": 0, "values": {}}
        
        return grouped
    
    def _create_empty_nested_groups(self, field1, field2, all_group_values, field_type):
        """Create empty nested group structure when no data matches filters"""
        grouped = {}
        for value1 in all_group_values[field1]:
            grouped[value1] = {}
            for value2 in all_group_values[field2]:
                if field_type == "numeric":
                    grouped[value1][value2] = {
                        "count": 0,
                        "min": None,
                        "max": None,
                        "sum": None,
                    }
                else:
                    grouped[value1][value2] = {"count": 0, "values": {}}
        return grouped

    def parse_filter_string(
        self, filter_string: str
    ) -> List[Tuple[str, str, Union[str, List[str]]]]:
        """Parse filter string into (field_name, operator, value) tuples."""
        filters = []
        for part in filter_string.split(","):
            if "=" in part:
                key_op, value = part.split("=", 1)
                key_op = key_op.strip()
                value = value.strip()

                # Parse operator
                if "__min" in key_op:
                    filters.append((key_op.replace("__min", ""), "gte", value))
                elif "__max" in key_op:
                    filters.append((key_op.replace("__max", ""), "lte", value))
                elif "__in" in key_op:
                    filters.append((key_op.replace("__in", ""), "in", value.split(";")))
                else:
                    # Use default equality filtering (no explicit operator)
                    filters.append((key_op, None, value))
        return filters

    def _validate_field_operator(
        self, field_name: str, operator: str, numeric_fields: set, string_fields: set
    ) -> None:
        """Validate that the operator is appropriate for the field type."""
        # None operator represents default equality filtering, always valid
        if operator is None:
            return

        if field_name in numeric_fields and operator not in self.NUMERIC_OPERATORS:
            raise ValueError(
                f"Operator '{operator}' is not supported for numeric field '{field_name}'."
            )

        if field_name in string_fields and operator not in self.STRING_OPERATORS:
            raise ValueError(
                f"Operator '{operator}' is not supported for string field '{field_name}'."
            )

        # Specific validation for string fields with numeric operators
        if field_name in string_fields and operator in {"gte", "lte"}:
            raise ValueError(
                f"Min/max operations are not supported for string field '{field_name}'."
            )

    def _build_exists_subquery(
        self,
        scenario_id: int,
        field_name: str,
        operator: str,
        value: Union[str, List[str]],
        numeric_fields: set,
    ) -> QuerySet:
        """Build EXISTS subquery for the given filter condition."""
        exists_subquery = ScenarioDataMetrics.objects.filter(
            scenario_id=scenario_id, feature_id=OuterRef("feature_id"), key=field_name
        )

        if field_name in numeric_fields:
            # Handle numeric field operations
            try:
                numeric_val = float(value)
                if operator == "gte":
                    exists_subquery = exists_subquery.filter(
                        numeric_value__gte=numeric_val
                    )
                elif operator == "lte":
                    exists_subquery = exists_subquery.filter(
                        numeric_value__lte=numeric_val
                    )
                else:  # operator is None (default equality)
                    exists_subquery = exists_subquery.filter(numeric_value=numeric_val)
            except (ValueError, TypeError):
                raise ValueError(
                    f"Invalid numeric value '{value}' for field '{field_name}'."
                )
        else:
            # Handle string field operations
            if operator == "in":
                # Ensure value is a list for 'in' operations
                value_list = value if isinstance(value, list) else [value]
                exists_subquery = exists_subquery.filter(string_value__in=value_list)
            else:  # operator is None (default equality)
                exists_subquery = exists_subquery.filter(string_value=value)

        return exists_subquery
