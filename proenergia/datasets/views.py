from django.db import transaction
from django.db.models import Count, FloatField, Max, Min, Sum, TextField
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
from rest_framework.response import Response
from rest_framework.views import APIView

from .filters import ScenarioDataFilter, VectorDatasetFilter
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
    """Lists VectorDatasets that are public and approved. For logged-in superadmin users, it returns all datasets."""

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
    """Returns information about a specific VectorDataset."""

    queryset = VectorDataset.objects.all()
    serializer_class = VectorDatasetSerializer
    permission_classes = [PublicApprovedDataset]


class DataModelListView(ListAPIView):
    """Lists all available DataModel entries."""

    queryset = DataModel.objects.all()
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


class SummaryView(APIView):
    """
    Returns statistics for a metadata field across all data entries for a specific Scenario.

    For string fields: returns the count of each unique value.
    For numeric fields (int/float): returns min, max, sum, and total count.

    Filters can be applied with the `?q=` query param.
    Numeric columns can be filtered by min and max values, example: `?q=Pop__min=1000` or `?q=Pop__max=1000`.
    String columns can be filtered by a single or multiple values, example: `?q=Posto=Maputo` or `?q=Posto__in=Maputo;Tefe`. Separate values with a semi-colon (`;`).

    It's possible to combine multiple filters: `?q=Pop__min=1000,Pop__max=2000,Posto=Maputo`.
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

        # Apply filters from query parameters
        filterset = ScenarioDataFilter(request.GET, queryset=queryset)
        if filterset.is_valid():
            queryset = filterset.qs

        # Get all values for the specified key from metadata
        entries_with_key = queryset.filter(metadata__has_key=key)

        if not entries_with_key.exists():
            return Response(
                {"error": f"No data found for key '{key}'."},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            with transaction.atomic():
                query = entries_with_key.annotate(
                    key=Cast(KT(f"metadata__{key}"), FloatField())
                ).aggregate(Max("key"), Min("key"), Sum("key"), Count("key"))

                summary = {
                    "key": key,
                    "type": "numeric",
                    "count": query.get("key__count"),
                    "min": query.get("key__min"),
                    "max": query.get("key__max"),
                    "sum": query.get("key__sum"),
                }
        except (ProgrammingError, DataError, InternalError):
            query = (
                entries_with_key.annotate(key=Cast(KT(f"metadata__{key}"), TextField()))
                .values("key")
                .annotate(count=Count("id"))
            )

            summary = {
                "key": key,
                "type": "string",
                "count": sum([i.get("count") for i in query]),
                "values": dict([(i.get("key"), i.get("count")) for i in query]),
            }

        return Response(summary)
