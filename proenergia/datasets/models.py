from os.path import splitext

from django.conf import settings
from django.contrib.postgres.indexes import GinIndex
from django.core.exceptions import ObjectDoesNotExist
from django.core.validators import FileExtensionValidator
from django.db import models
from django.db.models.fields.files import default_storage
from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver
from django.utils.text import slugify

from proenergia.datasets.tasks import (
    generate_pmtiles,
    generate_scenario_pmtiles,
    import_scenario_data_csv,
)


class VectorDataset(models.Model):
    name = models.CharField(max_length=155, unique=True)
    description = models.TextField(max_length=2000, null=True, blank=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, models.PROTECT, related_name="vector_datasets"
    )
    last_updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, models.PROTECT, related_name="+"
    )
    source = models.CharField(max_length=155, blank=True, null=True)
    is_public = models.BooleanField(default=False)
    is_approved = models.BooleanField(default=False)

    def __str__(self):
        return self.name

    def latest_file(self):
        try:
            return self.files.filter(status="ready").latest("created")
        except ObjectDoesNotExist:
            return None

    class Meta:
        ordering = ["id"]


STATUS = [
    ("created", "Created"),
    ("processing", "Processing"),
    ("ready", "Ready"),
    ("error", "Error"),
]


def generate_vector_file_name(instance, filename):
    """Generate a filename with the slugified dataset name,
    the version of the dataset and the file extension."""
    name, extension = splitext(filename)
    version = instance.dataset.files.count() + 1

    return f"vector/{slugify(instance.dataset.name)}_v{version}{extension}"


class VectorFile(models.Model):
    dataset = models.ForeignKey(VectorDataset, models.PROTECT, related_name="files")
    created = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, models.PROTECT, related_name="vector_files"
    )
    status = models.CharField(max_length=155, choices=STATUS, default="created")
    file = models.FileField(
        upload_to=generate_vector_file_name,
        unique=True,
        validators=[
            FileExtensionValidator(allowed_extensions=["geojson", "gpkg", "zip", "kml"])
        ],
    )
    error_message = models.TextField(default="", blank=True, null=True)

    def __str__(self):
        return f"{self.dataset} ({self.created})"

    class Meta:
        ordering = ["id"]


@receiver(post_save, sender=VectorFile)
def trigger_generate_pmtiles(sender, instance, created, **kwargs):
    """Trigger generate_pm_tiles Celery task when a new VectorFile instance is created."""
    if created:
        generate_pmtiles.delay(instance.id)


@receiver(pre_delete, sender=VectorFile)
def delete_vector_file(sender, instance, **kwargs):
    """
    Delete the file from storage when a VectorFile instance is deleted
    """
    if instance.file:
        # Using default_storage for better compatibility with different storage backends
        if default_storage.exists(instance.file.name):
            default_storage.delete(instance.file.name)


class DataModel(models.Model):
    name = models.CharField(max_length=155, unique=True)
    filter_fields = models.JSONField(
        default=list,
        help_text="""A list containing JSON objects following this structure: {"label": "Field label", "description": "Field description", "column": "File/Database column name"}""",
    )
    popup_fields = models.JSONField(
        default=list,
        help_text="""A list containing JSON objects following this structure: {"label": "Field label", "description": "Field description", "column": "File/Database column name", "unit": "Unit of measurement"}""",
    )
    summary_fields = models.JSONField(
        default=list(),
        help_text="""A list containing JSON objects following this structure: {"label": "Field label", "description": "Field description", "columns": ["column_1", "column_2"], "unit": "Unit of measurement", "method": "sum", "group_by": "column to aggregate data (optional)"}""",
    )
    metric_field_types = models.JSONField(
        default=dict,
        help_text="""Mapping of field names to their data types for metrics extraction. Structure: {'field_name': 'numeric', 'field_name_2': 'string'}. This is automatically populated from data introspection.""",
    )
    visualization_column = models.CharField(
        max_length=155,
        help_text="Column on the model results data file whose values will be used to define the data-driven visualization style.",
        blank=True,
        null=True,
    )
    color_coding = models.JSONField(
        default=list,
        help_text="""A list containing JSON objects following this structure: {"value": "visualization column value", "color": "#000000"}""",
    )
    contextual_layers = models.ManyToManyField(
        VectorDataset,
        null=True,
        blank=True,
        related_name="models",
        help_text="Vector datasets that can be visualized together with the model data.",
    )
    updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name}"

    class Meta:
        ordering = ["id"]


class Scenario(models.Model):
    name = models.CharField(max_length=155, unique=True)
    model = models.ForeignKey(
        DataModel, on_delete=models.PROTECT, related_name="scenarios"
    )
    vector_dataset = models.ForeignKey(VectorDataset, on_delete=models.PROTECT)

    def __str__(self):
        return f"{self.model.name} - {self.name}"

    def latest_file(self):
        try:
            return self.files.filter(status="ready").latest("created")
        except ObjectDoesNotExist:
            return None

    class Meta:
        ordering = ["id"]


def generate_scenario_file_name(instance, filename):
    """Generate a filename with the slugified scenario name,
    the version of the scenario and the file extension."""
    name, extension = splitext(filename)
    version = instance.scenario.files.count() + 1

    return f"scenarios/{slugify(instance.scenario.name)}_v{version}{extension}"


class ScenarioFile(models.Model):
    scenario = models.ForeignKey(Scenario, models.PROTECT, related_name="files")
    created = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, models.PROTECT, related_name="scenario_files"
    )
    status = models.CharField(max_length=155, choices=STATUS, default="created")
    file = models.FileField(
        upload_to=generate_scenario_file_name,
        unique=True,
        validators=[FileExtensionValidator(allowed_extensions=["csv"])],
    )
    error_message = models.TextField(default="", blank=True, null=True)

    def __str__(self):
        return f"{self.scenario} ({self.created})"

    class Meta:
        ordering = ["id"]


@receiver(post_save, sender=ScenarioFile)
def trigger_generate_scenario_pmtiles(sender, instance, created, **kwargs):
    """Trigger generate_scenario_pmtiles Celery task when a new ScenarioFile instance is created."""
    if created:
        generate_scenario_pmtiles.delay(instance.id)
        import_scenario_data_csv.delay(instance.id)


class ScenarioData(models.Model):
    feature_id = models.IntegerField()
    scenario = models.ForeignKey(Scenario, models.PROTECT, related_name="data")
    metadata = models.JSONField(default=dict)

    def __str__(self):
        return f"{self.feature_id} - {self.scenario}"

    class Meta:
        ordering = ["id"]
        unique_together = [["feature_id", "scenario"]]
        indexes = [
            models.Index(fields=["feature_id", "scenario"]),
            GinIndex(fields=["metadata"]),
        ]


class ScenarioDataMetrics(models.Model):
    """
    Denormalized metrics table for fast aggregations.
    Stores extracted key-value pairs from ScenarioData.metadata for commonly queried fields.
    """

    scenario = models.ForeignKey(Scenario, models.CASCADE, related_name="metrics")
    feature_id = models.IntegerField()
    key = models.CharField(max_length=255, db_index=True)
    numeric_value = models.DecimalField(
        max_digits=20, decimal_places=6, null=True, blank=True, db_index=True
    )
    string_value = models.TextField(null=True, blank=True, db_index=True)

    def __str__(self):
        return f"{self.scenario_id} - {self.feature_id} - {self.key}"

    class Meta:
        ordering = ["id"]
        unique_together = [["scenario", "feature_id", "key"]]
        indexes = [
            models.Index(fields=["scenario", "key", "numeric_value"]),
            models.Index(fields=["scenario", "key", "string_value"]),
            models.Index(fields=["scenario", "feature_id"]),
        ]
