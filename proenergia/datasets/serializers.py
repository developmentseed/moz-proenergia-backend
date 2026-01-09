from rest_framework import serializers

from .models import Scenario, ScenarioFile, VectorDataset, VectorFile


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


class ScenarioSerializer(serializers.ModelSerializer):
    model_file = serializers.SerializerMethodField()
    model = serializers.ReadOnlyField(source="model.name")
    filter_fields = serializers.ReadOnlyField(source="model.filter_fields")
    popup_fields = serializers.ReadOnlyField(source="model.popup_fields")

    class Meta:
        model = Scenario
        fields = [
            "id",
            "name",
            "model",
            "model_file",
            "filter_fields",
            "popup_fields",
        ]

    def get_model_file(self, obj):
        try:
            # update status to ready when we have the file conversion working
            model_file = obj.files.latest("created")
            return model_file.file.name
        except ScenarioFile.DoesNotExist:
            return None
