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
    - **group_by** (optional): Group results by a string field

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
        "group_by": "Admin_1"  // Only when grouping used
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
