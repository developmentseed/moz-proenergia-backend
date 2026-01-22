from os.path import splitext

from django.conf import settings
from django.core.validators import FileExtensionValidator
from django.db import models
from django.db.models.fields.files import default_storage
from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver
from django.utils.text import slugify

from proenergia.datasets.tasks import generate_pmtiles


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

    def __str__(self):
        return f"{self.dataset} ({self.created})"

    class Meta:
        ordering = ["id"]


@receiver(post_save, sender=VectorFile)
def trigger_generate_pm_tiles(sender, instance, created, **kwargs):
    """Trigger generate_pm_tiles Celery task when a new VectorFile instance is created.
    Only runs when not in test mode.
    """
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
        default=list(),
        help_text="A list containing JSON objects following this structure: {'label': 'Field label', 'description': 'Field description', 'column': 'File/Database column name'}",
    )
    popup_fields = models.JSONField(
        default=list(),
        help_text="A list containing JSON objects following this structure: {'label': 'Field label', 'description': 'Field description', 'column': 'File/Database column name'}",
    )

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
        return f"{self.name}"

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

    def __str__(self):
        return f"{self.scenario} ({self.created})"

    class Meta:
        ordering = ["id"]
