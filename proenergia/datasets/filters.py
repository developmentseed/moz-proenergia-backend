from django_filters import (
    CharFilter,
    DateFromToRangeFilter,
    FilterSet,
    OrderingFilter,
)

from .models import ScenarioData, VectorDataset


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


class ScenarioDataFilter(FilterSet):
    q = CharFilter(
        field_name="metadata",
        method="filter_metadata",
        help_text="Filter by the metadata field.",
    )

    def split_values(self, value):
        return [
            [i.strip() for i in t.split("=")]  # remove leading and ending spaces
            for t in value.split(",")
            if len(t.split("=")) == 2
        ]

    def filter_metadata(self, queryset, name, value):
        for query in self.split_values(value):
            if "__min" in query[0] or "__max" in query[0]:
                # handle both int values and other lookup options like __exact or __contains
                key = f"metadata__{query[0].replace('__min', '__gte').replace('__max', '__lte')}"
                try:
                    value = int(query[1])
                except ValueError:
                    value = query[1]
            elif "__in" in query[0]:
                key = f"metadata__{query[0]}"
                value = query[1].split(";")
            else:
                key = f"metadata__{query[0]}"
                value = query[1]
            queryset = queryset.filter(**{key: value})
        return queryset

    class Meta:
        model = ScenarioData
        fields = ["q"]
