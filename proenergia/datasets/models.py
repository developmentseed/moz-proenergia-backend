from django.conf import settings
from django.db import models


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

    class Meta:
        ordering = ["id"]
