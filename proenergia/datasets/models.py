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
from django.utils.translation import gettext_lazy as _

from proenergia.datasets.tasks import (
    generate_pmtiles,
    generate_scenario_pmtiles,
)
from proenergia.datasets.utils import get_file_variant


class VectorDataset(models.Model):
    name = models.CharField(_("name"), max_length=155, unique=True)
    description = models.TextField(
        _("description"), max_length=2000, null=True, blank=True
    )
    created = models.DateTimeField(_("created"), auto_now_add=True)
    updated = models.DateTimeField(_("updated"), auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        models.PROTECT,
        verbose_name=_("created by"),
        related_name="vector_datasets",
    )
    last_updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        models.PROTECT,
        verbose_name=_("last updated by"),
        related_name="+",
    )
    source = models.CharField(_("source"), max_length=155, blank=True, null=True)
    is_public = models.BooleanField(_("is public"), default=False)
    is_approved = models.BooleanField(_("is approved"), default=False)

    def __str__(self):
        return self.name

    def latest_file(self):
        try:
            return self.files.filter(status="ready").latest("created")
        except ObjectDoesNotExist:
            return None

    class Meta:
        ordering = ["id"]
        verbose_name = _("vector dataset")
        verbose_name_plural = _("vector datasets")


STATUS = [
    ("created", _("Created")),
    ("processing", _("Processing")),
    ("ready", _("Ready")),
    ("error", _("Error")),
]


def generate_vector_file_name(instance, filename):
    """Generate a filename with the slugified dataset name,
    the version of the dataset and the file extension."""
    name, extension = splitext(filename)
    version = instance.dataset.files.count() + 1

    return f"vector/{slugify(instance.dataset.name)}_v{version}{extension}"


class VectorFile(models.Model):
    dataset = models.ForeignKey(
        VectorDataset,
        models.PROTECT,
        verbose_name=_("dataset"),
        related_name="files",
    )
    created = models.DateTimeField(_("created"), auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        models.PROTECT,
        verbose_name=_("created by"),
        related_name="vector_files",
    )
    status = models.CharField(
        _("status"), max_length=155, choices=STATUS, default="created"
    )
    file = models.FileField(
        _("file"),
        upload_to=generate_vector_file_name,
        unique=True,
        validators=[
            FileExtensionValidator(allowed_extensions=["geojson", "gpkg", "zip", "kml"])
        ],
    )
    error_message = models.TextField(
        _("error message"), default="", blank=True, null=True
    )

    def __str__(self):
        return f"{self.dataset} ({self.created})"

    class Meta:
        ordering = ["id"]
        verbose_name = _("vector file")
        verbose_name_plural = _("vector files")


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
        # Delete uploaded file and derived formats
        for file in [
            instance.file.name,
            get_file_variant(instance.file.name, "fgb"),
            get_file_variant(instance.file.name, "pmtiles"),
        ]:
            if default_storage.exists(file):
                default_storage.delete(file)


class DataModel(models.Model):
    name = models.CharField(_("name"), max_length=155, unique=True)
    presentation_order = models.IntegerField(
        _("presentation order"),
        default=0,
        help_text=_("Order of the item to be presented in the application."),
    )
    description = models.TextField(
        _("description"), max_length=2000, null=True, blank=True
    )
    filter_fields = models.JSONField(
        _("filter fields"),
        default=list,
        help_text=_(
            """A list containing JSON objects following this structure: {"label": "Field label", "description": "Field description", "column": "File/Database column name", "label_pt": "Label in Portuguese", "description_pt": "Description in Portuguese"}"""
        ),
    )
    popup_fields = models.JSONField(
        _("popup fields"),
        default=list,
        help_text=_(
            """A list containing JSON objects following this structure: {"label": "Field label", "description": "Field description", "column": "File/Database column name", "unit": "Unit of measurement", "label_pt": "Label in Portuguese", "description_pt": "Description in Portuguese"}"""
        ),
    )
    summary_fields = models.JSONField(
        _("summary fields"),
        default=list(),
        help_text=_("""A list containing JSON objects following this structure:<br>
            {"label": "Field label", "description": "Field description", "columns": ["column_1", "column_2"], "unit": "Unit of measurement (optional)", "method": "One of: sum, average, count, min, max", "group_by": "column to aggregate data (optional)", "category": "The category where the field will be shown in the frontend summary section (optional)", "chartType": "One of: bar, donut, stacked, column, area, highlight (optional)", "hasDecimal": false}
            <br>The "method" field is optional and defaults to "sum". The "hasDecimal" field is optional and defaults to false. You can also add "label_pt" and "description_pt" fields for translated labels and descriptions.
        """),
    )
    metric_field_types = models.JSONField(
        _("metric field types"),
        default=dict,
        help_text=_(
            "Mapping of field names to their data types for metrics extraction. Structure: {'field_name': 'numeric', 'field_name_2': 'string'}. This is automatically populated from data introspection."
        ),
    )
    visualization_column = models.CharField(
        _("visualization column"),
        max_length=155,
        help_text=_(
            "Column on the model results data file whose values will be used to define the data-driven visualization style."
        ),
        blank=True,
        null=True,
    )
    color_coding = models.JSONField(
        _("color coding"),
        default=list,
        help_text=_(
            """A list containing JSON objects following this structure: {"value": "visualization column value", "color": "#000000"}"""
        ),
    )
    contextual_layers = models.ManyToManyField(
        VectorDataset,
        verbose_name=_("contextual layers"),
        null=True,
        blank=True,
        related_name="models",
        help_text=_(
            "Vector datasets that can be visualized together with the model data."
        ),
    )

    def __str__(self):
        return f"{self.name}"

    class Meta:
        ordering = ["presentation_order", "id"]
        verbose_name = _("data model")
        verbose_name_plural = _("data models")


class Scenario(models.Model):
    name = models.CharField(_("name"), max_length=155, unique=True)
    presentation_order = models.IntegerField(
        _("presentation order"),
        default=0,
        help_text=_("Order of the item to be presented in the application."),
    )
    model = models.ForeignKey(
        DataModel,
        on_delete=models.CASCADE,
        verbose_name=_("model"),
        related_name="scenarios",
    )
    vector_dataset = models.ForeignKey(
        VectorDataset,
        on_delete=models.PROTECT,
        verbose_name=_("vector dataset"),
    )

    def __str__(self):
        return f"{self.model.name} - {self.name}"

    def latest_file(self):
        try:
            return self.files.filter(status="ready").latest("created")
        except ObjectDoesNotExist:
            return None

    class Meta:
        ordering = ["presentation_order", "id"]
        verbose_name = _("scenario")
        verbose_name_plural = _("scenarios")


def generate_scenario_file_name(instance, filename):
    """Generate a filename with the slugified scenario name,
    the version of the scenario and the file extension."""
    name, extension = splitext(filename)
    version = instance.scenario.files.count() + 1

    return f"scenarios/{slugify(instance.scenario.name)}_v{version}{extension}"


class ScenarioFile(models.Model):
    scenario = models.ForeignKey(
        Scenario,
        models.CASCADE,
        verbose_name=_("scenario"),
        related_name="files",
    )
    created = models.DateTimeField(_("created"), auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        models.PROTECT,
        verbose_name=_("created by"),
        related_name="scenario_files",
    )
    status = models.CharField(
        _("status"), max_length=155, choices=STATUS, default="created"
    )
    file = models.FileField(
        _("file"),
        upload_to=generate_scenario_file_name,
        unique=True,
        validators=[FileExtensionValidator(allowed_extensions=["csv"])],
    )
    low_zoom_as_points = models.BooleanField(
        _("Represent features as points in lower zoom levels"),
        default=False,
        help_text=_(
            "If enabled, features will be represented as points in lower zoom levels. It's recommended for large datasets composed by many squared polygons."
        ),
    )
    error_message = models.TextField(
        _("error message"), default="", blank=True, null=True
    )

    def __str__(self):
        return f"{self.scenario} ({self.created})"

    class Meta:
        ordering = ["id"]
        verbose_name = _("scenario file")
        verbose_name_plural = _("scenario files")


@receiver(pre_delete, sender=ScenarioFile)
def delete_scenario_file(sender, instance, **kwargs):
    """
    Delete the file from storage when a ScenarioFile instance is deleted
    """
    if instance.file:
        # Delete uploaded file and derived formats
        for file in [
            instance.file.name,
            get_file_variant(instance.file.name, "fgb"),
            get_file_variant(instance.file.name, "pmtiles"),
        ]:
            if default_storage.exists(file):
                default_storage.delete(file)


@receiver(post_save, sender=ScenarioFile)
def trigger_generate_scenario_pmtiles(sender, instance, created, **kwargs):
    """Trigger generate_scenario_pmtiles Celery task when a new ScenarioFile instance is created."""
    if created:
        generate_scenario_pmtiles.delay(instance.id)


class ScenarioData(models.Model):
    feature_id = models.IntegerField(_("feature id"))
    scenario = models.ForeignKey(
        Scenario,
        models.CASCADE,
        verbose_name=_("scenario"),
        related_name="data",
    )
    metadata = models.JSONField(_("metadata"), default=dict)

    def __str__(self):
        return f"{self.feature_id} - {self.scenario}"

    class Meta:
        ordering = ["id"]
        unique_together = [["feature_id", "scenario"]]
        verbose_name = _("scenario data")
        verbose_name_plural = _("scenario data")
        indexes = [
            models.Index(fields=["feature_id", "scenario"]),
            GinIndex(fields=["metadata"]),
        ]


class ScenarioDataMetrics(models.Model):
    """
    Denormalized metrics table for fast aggregations.
    Stores extracted key-value pairs from ScenarioData.metadata for commonly queried fields.
    """

    scenario = models.ForeignKey(
        Scenario,
        models.CASCADE,
        verbose_name=_("scenario"),
        related_name="metrics",
    )
    feature_id = models.IntegerField(_("feature id"))
    key = models.CharField(_("key"), max_length=255, db_index=True)
    numeric_value = models.DecimalField(
        _("numeric value"),
        max_digits=20,
        decimal_places=6,
        null=True,
        blank=True,
        db_index=True,
    )
    string_value = models.TextField(
        _("string value"), null=True, blank=True, db_index=True
    )

    def __str__(self):
        return f"{self.scenario_id} - {self.feature_id} - {self.key}"

    class Meta:
        ordering = ["id"]
        unique_together = [["scenario", "feature_id", "key"]]
        verbose_name = _("scenario data metric")
        verbose_name_plural = _("scenario data metrics")
        indexes = [
            models.Index(fields=["scenario", "key", "numeric_value"]),
            models.Index(fields=["scenario", "key", "string_value"]),
            models.Index(fields=["scenario", "feature_id"]),
        ]
