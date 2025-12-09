from rest_framework import serializers

from .models import VectorDataset


class VectorDatasetSerializer(serializers.ModelSerializer):
    created_by = serializers.ReadOnlyField(source="created_by.name")
    last_updated_by = serializers.ReadOnlyField(source="last_updated_by.name")

    class Meta:
        model = VectorDataset
        fields = [
            "id",
            "name",
            "description",
            "source",
            "created",
            "updated",
            "created_by",
            "last_updated_by",
            "is_public",
            "is_approved",
        ]
