from typing import Optional

from rest_framework import serializers

from .models import (
    DataModel,
    RasterDataset,
    Scenario,
    ScenarioData,
    ScenarioFile,
    VectorDataset,
)


class DatasetSerializer(serializers.ModelSerializer):
    created_by = serializers.ReadOnlyField(source="created_by.name")
    last_updated_by = serializers.ReadOnlyField(source="last_updated_by.name")
    raw_file = serializers.SerializerMethodField()
    name = serializers.CharField(source="name_en")
    description = serializers.CharField(source="description_en")

    def get_raw_file(self, obj):
        f = obj.latest_file()
        return f.file.name if f else None


class VectorDatasetSerializer(DatasetSerializer):
    class Meta:
        model = VectorDataset
        fields = [
            "id",
            "name",
            "name_pt",
            "description",
            "description_pt",
            "created",
            "updated",
            "created_by",
            "last_updated_by",
            "source",
            "contact",
            "source",
            "contact",
            "published",
            "temporal_extent",
            "crs",
            "frequency",
            "lineage",
            "license",
            "attribute",
            "is_public",
            "is_approved",
            "raw_file",
        ]


class RasterDatasetSerializer(DatasetSerializer):
    class Meta:
        model = RasterDataset
        fields = [
            "id",
            "name",
            "name_pt",
            "description",
            "description_pt",
            "created",
            "updated",
            "created_by",
            "last_updated_by",
            "source",
            "contact",
            "source",
            "contact",
            "published",
            "temporal_extent",
            "crs",
            "frequency",
            "lineage",
            "license",
            "attribute",
            "is_public",
            "is_approved",
            "raw_file",
        ]


class ScenarioSerializer(serializers.ModelSerializer):
    model_file = serializers.SerializerMethodField()
    vector_dataset = VectorDatasetSerializer()
    name = serializers.CharField(source="name_en")

    class Meta:
        model = Scenario
        fields = [
            "id",
            "name",
            "name_pt",
            "presentation_order",
            "vector_dataset",
            "model_file",
        ]

    def get_model_file(self, obj: Scenario) -> Optional[str]:
        try:
            model_file = obj.latest_file()
            return model_file.file.name if model_file else None
        except ScenarioFile.DoesNotExist:
            return None


class DataModelSerializer(serializers.ModelSerializer):
    scenarios = ScenarioSerializer(many=True, read_only=True)
    name = serializers.CharField(source="name_en")
    description = serializers.CharField(source="description_en")

    class Meta:
        model = DataModel
        fields = [
            "id",
            "name",
            "name_pt",
            "description",
            "description_pt",
            "presentation_order",
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
