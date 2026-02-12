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
    Compute statistical summaries on multiple scenario metadata fields in a single request.

    This endpoint provides efficient aggregation of scenario data fields, supporting filtering
    and grouping operations. All requested fields must be configured in the DataModel's
    summary_fields array with appropriate type indicators.

    **URL Pattern:** `/api/v1/scenario/{pk}/summaries/`

    **Authentication:** Public read access (IsAuthenticatedOrReadOnly)

    ## Query Parameters

    ### Required Parameters
    - **fields** (string): Comma-separated list of field names to summarize
      - Must be configured in DataModel.summary_fields
      - Example: `fields=Pop2030` or `fields=Pop2030,Technology2030`

    ### Optional Parameters
    - **q** (string): Filter expression using field operators
      - Multiple filters separated by commas
      - Example: `q=Admin_1=Maputo,Pop2030__min=10000`

    - **group_by** (string): Single string field name for grouping results
      - Must be a string-type field configured in summary_fields
      - Example: `group_by=Technology2030`

    ## Filter Syntax

    ### Numeric Field Operators
    - `field__min=value` - Greater than or equal to (>=)
    - `field__max=value` - Less than or equal to (<=)
    - `field=value` - Exact equality (=)

    ### String Field Operators
    - `field=value` - Exact match
    - `field__in=value1;value2;value3` - Match any value in semicolon-separated list

    ### Multiple Filters
    Combine filters with commas: `q=field1=value1,field2__min=value2,field3__in=val1;val2`

    ## Response Format

    ### Base Response Structure
    ```json
    {
        "scenario_id": 1,
        "filters_applied": "Admin_1=Maputo",
        "summaries": {
            "field_name": {
                "type": "numeric|string",
                // ... field summary
            }
        },
        "group_by": "field_name"  // Only when grouping is used
    }
    ```

    ### Numeric Field Summary
    ```json
    {
        "type": "numeric",
        "count": 726530,
        "min": 3.6935,
        "max": 3620782.55,
        "sum": 38689101.975,
        "grouped": {  // Only when group_by is used
            "group_value": {
                "count": 7354,
                "min": 3.6935,
                "max": 3620782.55,
                "sum": 4466719.8774
            }
        }
    }
    ```

    ### String Field Summary
    ```json
    {
        "type": "string",
        "count": 726530,
        "values": {
            "ExistingGrid": 3996,
            "GridExtension": 4420,
            "MiniGrid_PV": 489,
            "SHS": 717625
        },
        "grouped": {  // Only when group_by is used
            "group_value": {
                "count": 1000,
                "values": {
                    "ExistingGrid": 500,
                    "SHS": 500
                }
            }
        }
    }
    ```

    ## Usage Examples

    ### Example 1: Single Numeric Field
    ```
    GET /api/v1/scenario/1/summaries/?fields=Pop2030

    Response:
    {
        "scenario_id": 1,
        "filters_applied": "",
        "summaries": {
            "Pop2030": {
                "type": "numeric",
                "count": 726530,
                "min": 3.6935,
                "max": 3620782.55,
                "sum": 38689101.975
            }
        }
    }
    ```

    ### Example 2: Multiple Fields
    ```
    GET /api/v1/scenario/1/summaries/?fields=Pop2030,Technology2030

    Response:
    {
        "scenario_id": 1,
        "filters_applied": "",
        "summaries": {
            "Pop2030": {
                "type": "numeric",
                "count": 726530,
                "min": 3.6935,
                "max": 3620782.55,
                "sum": 38689101.975
            },
            "Technology2030": {
                "type": "string",
                "count": 726530,
                "values": {
                    "ExistingGrid": 3996,
                    "GridExtension": 4420,
                    "MiniGrid_PV": 489,
                    "SHS": 717625
                }
            }
        }
    }
    ```

    ### Example 3: With Filters
    ```
    GET /api/v1/scenario/1/summaries/?fields=Pop2030&q=Admin_1=Maputo

    Response:
    {
        "scenario_id": 1,
        "filters_applied": "Admin_1=Maputo",
        "summaries": {
            "Pop2030": {
                "type": "numeric",
                "count": 7354,
                "min": 3.6935,
                "max": 3620782.55,
                "sum": 4466719.8774
            }
        }
    }
    ```

    ### Example 4: With Grouping
    ```
    GET /api/v1/scenario/1/summaries/?fields=Pop2030&group_by=Technology2030

    Response:
    {
        "scenario_id": 1,
        "filters_applied": "",
        "summaries": {
            "Pop2030": {
                "type": "numeric",
                "count": 726530,
                "min": 3.6935,
                "max": 3620782.55,
                "sum": 38689101.975,
                "grouped": {
                    "ExistingGrid": {
                        "count": 3996,
                        "min": 10024.154,
                        "max": 3620782.55,
                        "sum": 21523998.0701
                    },
                    "SHS": {
                        "count": 717625,
                        "min": 3.6935,
                        "max": 9999.8,
                        "sum": 15234567.89
                    }
                }
            }
        },
        "group_by": "Technology2030"
    }
    ```

    ### Example 5: Complex Query
    ```
    GET /api/v1/scenario/1/summaries/?fields=Pop2030&q=Pop2030__min=10000&group_by=Technology2030

    Response:
    {
        "scenario_id": 1,
        "filters_applied": "Pop2030__min=10000",
        "summaries": {
            "Pop2030": {
                "type": "numeric",
                "count": 250,
                "min": 10024.154,
                "max": 3620782.55,
                "sum": 21534893.919,
                "grouped": {
                    "ExistingGrid": {
                        "count": 249,
                        "min": 10024.154,
                        "max": 3620782.55,
                        "sum": 21523998.0701
                    },
                    "GridExtension": {
                        "count": 1,
                        "min": 10895.8489,
                        "max": 10895.8489,
                        "sum": 10895.8489
                    },
                    "MiniGrid_PV": {
                        "count": 0,
                        "min": null,
                        "max": null,
                        "sum": null
                    },
                    "SHS": {
                        "count": 0,
                        "min": null,
                        "max": null,
                        "sum": null
                    }
                }
            }
        },
        "group_by": "Technology2030"
    }
    ```

    ## Error Responses

    ### 400 Bad Request
    ```json
    {"error": "The 'fields' parameter is required."}
    {"error": "Field(s) not configured for summaries: InvalidField"}
    {"error": "Operator 'gte' is not supported for string field 'Technology2030'."}
    ```

    ### 404 Not Found
    ```json
    {"error": "No data found for field(s): Pop2030. Metrics may need to be regenerated."}
    {"error": "No data found for group by field 'Technology2030'."}
    ```

    ## Common Field Examples

    **Numeric Fields:** Pop2030, NewHHConnectionsTotal, GHI, GridCellArea, MGInvestmentCostTotal

    **String Fields:** Technology2030, Admin_1, District, Posto, Status

    **Note:** Available fields depend on the specific DataModel configuration for each scenario.
    Use the DataModel API endpoints to discover available fields for a scenario.
    """

    # Supported operators for each field type
    NUMERIC_OPERATORS = {"gte", "lte", "eq"}
    STRING_OPERATORS = {"eq", "in"}

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

        # 3. Get configured fields and validate ALL requested fields
        field_type_map = self._get_field_type_map(scenario.model)

        # Validate all fields are configured
        invalid_fields = [f for f in requested_fields if f not in field_type_map]
        if invalid_fields:
            return Response(
                {
                    "error": f"Field(s) not configured for summaries: {', '.join(invalid_fields)}"
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Check all fields have metrics data
        missing_data_fields = []
        for field in requested_fields:
            if not ScenarioDataMetrics.objects.filter(
                scenario=scenario, key=field
            ).exists():
                missing_data_fields.append(field)

        if missing_data_fields:
            return Response(
                {
                    "error": f"No data found for field(s): {', '.join(missing_data_fields)}. Metrics may need to be regenerated."
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        # 4. Parse and validate group_by parameter
        group_by = request.GET.get("group_by", "").strip()
        group_by_values = None

        if group_by:
            # Validate group_by field exists and is a string field
            if group_by not in field_type_map:
                return Response(
                    {
                        "error": f"Group by field '{group_by}' is not configured for summaries."
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if field_type_map[group_by] != "string":
                return Response(
                    {"error": f"Group by field '{group_by}' must be a string field."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Check group_by field has data
            if not ScenarioDataMetrics.objects.filter(
                scenario=scenario, key=group_by
            ).exists():
                return Response(
                    {"error": f"No data found for group by field '{group_by}'."},
                    status=status.HTTP_404_NOT_FOUND,
                )

            # Get all possible values for the group_by field (including those that might be filtered out)
            group_by_values = self._get_all_group_values(scenario, group_by)

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
            # Build query for this field
            metrics_query = ScenarioDataMetrics.objects.filter(
                scenario=scenario, key=field
            )

            # Apply feature_id filter if filters were provided
            if base_feature_subquery is not None:
                metrics_query = metrics_query.filter(
                    feature_id__in=base_feature_subquery
                )

            # Compute overall summary
            field_type = field_type_map[field]
            summary = self._compute_field_summary(metrics_query, field_type)

            # Add grouped summaries if group_by is provided
            if group_by and group_by_values:
                summary["grouped"] = self._compute_grouped_summaries(
                    scenario,
                    field,
                    field_type,
                    group_by,
                    group_by_values,
                    base_feature_subquery,
                )

            summaries[field] = summary

        # 7. Return successful response
        response = {
            "scenario_id": pk,
            "filters_applied": filter_params,
            "summaries": summaries,
        }

        if group_by:
            response["group_by"] = group_by

        return Response(response)

    def _get_field_type_map(self, model):
        """Build a mapping of field names to their types"""
        return {
            field["column"]: field.get("type", "string")
            for field in (model.summary_fields or [])
        }

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
        group_by_field,
        all_group_values,
        base_feature_subquery,
    ):
        """Compute summaries grouped by another field using efficient subqueries"""
        grouped = {}

        for group_value in all_group_values:
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
                    filters.append((key_op, "eq", value))
        return filters

    def _validate_field_operator(
        self, field_name: str, operator: str, numeric_fields: set, string_fields: set
    ) -> None:
        """Validate that the operator is appropriate for the field type."""
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
                elif operator == "eq":
                    exists_subquery = exists_subquery.filter(numeric_value=numeric_val)
            except (ValueError, TypeError):
                raise ValueError(
                    f"Invalid numeric value '{value}' for field '{field_name}'."
                )
        else:
            # Handle string field operations
            if operator == "eq":
                exists_subquery = exists_subquery.filter(string_value=value)
            elif operator == "in":
                # Ensure value is a list for 'in' operations
                value_list = value if isinstance(value, list) else [value]
                exists_subquery = exists_subquery.filter(string_value__in=value_list)

        return exists_subquery
