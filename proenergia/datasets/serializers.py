from rest_framework import serializers

from .models import VectorDataset, VectorFile


class VectorDatasetSerializer(serializers.ModelSerializer):
    created_by = serializers.ReadOnlyField(source="created_by.name")
    last_updated_by = serializers.ReadOnlyField(source="last_updated_by.name")
    raw_file = serializers.SerializerMethodField()

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
            "raw_file",
        ]

    def get_raw_file(self, obj):
        try:
            # update status to ready when we have the file conversion working
            vector_file = obj.files.latest("created")
            return vector_file.file.name
        except VectorFile.DoesNotExist:
            return None
