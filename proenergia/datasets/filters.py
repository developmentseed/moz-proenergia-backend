from django.db.models import Q
from django_filters import (
    CharFilter,
    DateFromToRangeFilter,
    FilterSet,
    NumberFilter,
    OrderingFilter,
)

from .models import DataModel, VectorDataset


class VectorDatasetFilter(FilterSet):
    name = CharFilter(field_name="name", lookup_expr="icontains")
    source = CharFilter(field_name="source", lookup_expr="icontains")
    created = DateFromToRangeFilter()
    updated = DateFromToRangeFilter()
    order_by = OrderingFilter(
        fields=("name", "id", "updated", "created"),
    )
    model = NumberFilter(field_name="models", method="filter_model", help_text="Filter")

    def filter_model(self, queryset, name, value):
        return queryset.filter(
            Q(models__id=value) | Q(scenario__model__id=value)
        ).distinct()

    class Meta:
        model = VectorDataset
        fields = ["name", "source", "created", "updated", "model"]


class DataModelFilter(FilterSet):
    name = CharFilter(field_name="name", lookup_expr="icontains")
    order_by = OrderingFilter(
        fields=("name", "id", "presentation_order"),
    )

    class Meta:
        model = DataModel
        fields = ["name"]
