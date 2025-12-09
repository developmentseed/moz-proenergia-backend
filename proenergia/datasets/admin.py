from django.contrib import admin

from .models import VectorDataset


@admin.register(VectorDataset)
class VectorDatasetAdmin(admin.ModelAdmin):
    list_display = ["id", "name", "updated", "is_public", "is_approved"]
    fields = ["name", "description", "source"]

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user

        obj.last_updated_by = request.user
        super().save_model(request, obj, form, change)
