from rest_framework import status
from rest_framework.generics import ListAPIView, RetrieveAPIView, get_object_or_404
from rest_framework.permissions import (
    SAFE_METHODS,
    BasePermission,
    IsAuthenticatedOrReadOnly,
)
from rest_framework.response import Response
from rest_framework.views import APIView

from .filters import VectorDatasetFilter
from .models import DataModel, Scenario, ScenarioData, VectorDataset
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
        else:
            return request.method in SAFE_METHODS and obj.is_public and obj.is_approved


class VectorDatasetListView(ListAPIView):
    serializer_class = VectorDatasetSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    pagination_class = StandardResultsSetPagination
    filterset_class = VectorDatasetFilter

    def get_queryset(self):
        queryset = VectorDataset.objects.select_related("created_by", "last_updated_by")
        if self.request.user and self.request.user.is_superuser:
            return queryset
        else:
            return queryset.filter(is_public=True, is_approved=True)


class VectorDatasetDetailView(RetrieveAPIView):
    queryset = VectorDataset.objects.all()
    serializer_class = VectorDatasetSerializer
    permission_classes = [PublicApprovedDataset]


class DataModelListView(ListAPIView):
    queryset = DataModel.objects.all()
    serializer_class = DataModelSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]


class DataModelDetailView(RetrieveAPIView):
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


class SummaryView(APIView):
    """
    Returns statistics for a metadata field across all data entries for a specific Scenario.

    For string fields: returns the count of each unique value
    For numeric fields (int/float): returns min, max, sum, and total count
    """

    permission_classes = [IsAuthenticatedOrReadOnly]

    def get(self, request, pk, key):
        # Verify scenario exists
        scenario = get_object_or_404(Scenario, id=pk)

        # Get all ScenarioData entries for this scenario
        queryset = ScenarioData.objects.filter(scenario=scenario)

        if not queryset.exists():
            return Response(
                {"error": "No data found for this scenario"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Get all values for the specified key from metadata
        entries_with_key = queryset.filter(metadata__has_key=key)

        if not entries_with_key.exists():
            return Response(
                {"error": f"Key '{key}' not found in metadata"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Extract all values for this key
        values = []
        for entry in entries_with_key:
            value = entry.metadata.get(key)
            if value is not None:
                values.append(value)

        if not values:
            return Response(
                {"error": f"No non-null values found for key '{key}'"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Determine data type from first value
        first_value = values[0]

        if isinstance(first_value, (int, float)):
            # Numeric field - return statistical summary
            numeric_values = [v for v in values if isinstance(v, (int, float))]

            summary = {
                "key": key,
                "type": "numeric",
                "count": len(numeric_values),
                "min": min(numeric_values) if numeric_values else None,
                "max": max(numeric_values) if numeric_values else None,
                "sum": sum(numeric_values) if numeric_values else None,
            }
        else:
            # String field - return count by value
            value_counts = {}
            for value in values:
                str_value = str(value)
                value_counts[str_value] = value_counts.get(str_value, 0) + 1

            summary = {
                "key": key,
                "type": "string",
                "count": len(values),
                "values": value_counts,
            }

        return Response(summary)
