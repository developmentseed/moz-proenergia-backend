from django_filters import (
    CharFilter,
    DateFromToRangeFilter,
    FilterSet,
    OrderingFilter,
)

from .models import VectorDataset


class VectorDatasetFilter(FilterSet):
    name = CharFilter(field_name="name", lookup_expr="icontains")
    source = CharFilter(field_name="source", lookup_expr="icontains")
    created = DateFromToRangeFilter()
    updated = DateFromToRangeFilter()
    order_by = OrderingFilter(
        fields=("name", "id", "updated", "created"),
    )

    class Meta:
        model = VectorDataset
        fields = ["name", "source", "created", "updated"]
