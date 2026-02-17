from rest_framework import status
from rest_framework.generics import ListAPIView, RetrieveAPIView, get_object_or_404
from rest_framework.permissions import (
    SAFE_METHODS,
    BasePermission,
    IsAuthenticatedOrReadOnly,
)
from rest_framework.response import Response
from rest_framework.views import APIView

from .aggregation import FilterParser, get_aggregator, CombinedFieldAggregator
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

    Orchestrates field summary computation using optimized aggregation strategies.
    Delegates complex logic to specialized components for better maintainability.

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

    Fields must be configured in DataModel.metric_field_types. Use DataModel API to discover available fields.
    """

    permission_classes = [IsAuthenticatedOrReadOnly]

    def get(self, request, pk):
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

        # 3. Get field type mapping and initialize filter parser
        field_type_map = scenario.model.metric_field_types or {}
        filter_parser = FilterParser(field_type_map) if field_type_map else None

        # 4. Parse and validate group_by parameter
        group_by_fields = []
        group_by_values = {}
        group_by_param = request.GET.get("group_by", "").strip()

        if group_by_param:
            # Parse comma-separated group_by fields
            group_by_fields = [
                f.strip() for f in group_by_param.split(",") if f.strip()
            ]

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

        # 5. Parse filter parameters
        filter_params = request.GET.get("q", "")

        # Validate filters if provided
        if filter_params and filter_parser:
            try:
                # Parse to validate format and field names
                filter_parser.parse_filter_string(filter_params)
            except ValueError as e:
                return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        # 6. Filter out fields that don't exist in the data
        # Pre-check which fields have data to avoid unnecessary processing
        fields_with_data = {}
        for field in requested_fields:
            # Check if field is configured
            if field not in field_type_map:
                continue

            # Check if field has any data
            if ScenarioDataMetrics.objects.filter(
                scenario=scenario, key=field
            ).exists():
                fields_with_data[field] = field_type_map[field]

        # 7. Use CombinedFieldAggregator for batch processing
        # This dramatically reduces the number of queries
        if fields_with_data:
            aggregator = CombinedFieldAggregator()

            # Use batch processing for all cases (0, 1, or 2 group_by fields)
            summaries = aggregator.compute_summaries_batch(
                scenario_id=scenario.id,
                fields=fields_with_data,
                group_fields=group_by_fields if group_by_fields else None,
                all_group_values=group_by_values if group_by_values else None,
                filter_parser=filter_parser,
                filter_string=filter_params if filter_params else None,
            )
        else:
            summaries = {}

        # Add empty results for fields without data or invalid fields
        for field in requested_fields:
            if field not in summaries:
                summaries[field] = {"count": 0}

        # 8. Return successful response
        response = {
            "scenario_id": pk,
            "filters_applied": filter_params,
            "summaries": summaries,
        }

        if group_by_fields:
            response["group_by"] = group_by_fields

        return Response(response)

    def _get_all_group_values(self, scenario, group_by_field):
        """Get all unique values for the group_by field in the scenario."""
        return list(
            ScenarioDataMetrics.objects.filter(scenario=scenario, key=group_by_field)
            .values_list("string_value", flat=True)
            .distinct()
            .order_by("string_value")
        )
