from django.conf import settings
from django.core.validators import FileExtensionValidator
from django.db import models
from django.db.models.fields.files import default_storage
from django.db.models.signals import pre_delete
from django.dispatch import receiver


class VectorDataset(models.Model):
    name = models.CharField(max_length=155)
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


class VectorFile(models.Model):
    dataset = models.ForeignKey(VectorDataset, models.PROTECT, related_name="files")
    created = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, models.PROTECT, related_name="vector_files"
    )
    status = models.CharField(max_length=155, choices=STATUS, default="created")
    file = models.FileField(
        upload_to="vector/",
        unique=True,
        validators=[
            FileExtensionValidator(allowed_extensions=["geojson", "gpkg", "zip", "kml"])
        ],
    )

    def __str__(self):
        return f"{self.dataset} ({self.created})"

    class Meta:
        ordering = ["id"]


@receiver(pre_delete, sender=VectorFile)
def delete_vector_file(sender, instance, **kwargs):
    """
    Delete the file from storage when a VectorFile instance is deleted
    """
    if instance.file:
        # Using default_storage for better compatibility with different storage backends
        if default_storage.exists(instance.file.name):
            default_storage.delete(instance.file.name)
