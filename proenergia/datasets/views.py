from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.permissions import (
    SAFE_METHODS,
    BasePermission,
    IsAuthenticatedOrReadOnly,
)

from .filters import VectorDatasetFilter
from .models import DataModel, VectorDataset
from .pagination import StandardResultsSetPagination
from .serializers import (
    DataModelSerializer,
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
