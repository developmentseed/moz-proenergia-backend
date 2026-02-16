from rest_framework import serializers

from .models import DataModel, Scenario, ScenarioData, ScenarioFile, VectorDataset


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
        vector_file = obj.latest_file()
        return vector_file.file.name if vector_file else None


class ScenarioSerializer(serializers.ModelSerializer):
    model_file = serializers.SerializerMethodField()

    class Meta:
        model = Scenario
        fields = [
            "id",
            "name",
            "model_file",
        ]

    def get_model_file(self, obj):
        try:
            model_file = obj.latest_file()
            return model_file.file.name if model_file else None
        except ScenarioFile.DoesNotExist:
            return None


class DataModelSerializer(serializers.ModelSerializer):
    scenarios = ScenarioSerializer(many=True, read_only=True)

    class Meta:
        model = DataModel
        fields = [
            "id",
            "name",
            "filter_fields",
            "popup_fields",
            "summary_fields",
            "metric_field_types",
            "visualization_column",
            "color_coding",
            "scenarios",
        ]


class ScenarioDataSerializer(serializers.ModelSerializer):
    class Meta:
        model = ScenarioData
        fields = ["feature_id", "metadata"]

    def to_representation(self, instance):
        """Flatten metadata contents to the root level of the response"""
        representation = super().to_representation(instance)

        # Extract metadata and remove it from root
        metadata = representation.pop("metadata", {})

        # Add feature_id first, then all metadata fields
        result = {"feature_id": representation["feature_id"]}

        # Merge metadata fields into root
        if metadata:
            result.update(metadata)

        return result
