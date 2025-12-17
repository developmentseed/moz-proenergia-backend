from django.contrib import admin, messages
from unfold.admin import ModelAdmin

from .models import VectorDataset, VectorFile


class PermissionBasedModelAdmin(ModelAdmin):
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(created_by=request.user)

    def has_module_permission(self, request):
        return request.user.is_staff

    def has_add_permission(self, request, obj=None):
        return request.user.is_staff

    def has_view_permission(self, request, obj=None):
        return self.is_owner_or_superuser(request, obj)

    def has_change_permission(self, request, obj=None):
        return self.is_owner_or_superuser(request, obj)

    def has_delete_permission(self, request, obj=None):
        return self.is_owner_or_superuser(request, obj)

    def is_owner_or_superuser(self, request, obj):
        if obj is None:
            return True
        if request.user == obj.created_by or request.user.is_superuser:
            return True
        return False


@admin.register(VectorDataset)
class VectorDatasetAdmin(PermissionBasedModelAdmin):
    list_display = ["id", "name", "updated", "is_public", "is_approved"]
    fields = ["name", "description", "source"]
    actions = ["make_public", "make_private", "approve", "disapprove"]

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user

        obj.last_updated_by = request.user
        super().save_model(request, obj, form, change)

    def confirmation_message(self, request, queryset, value):
        if queryset.count() == 1:
            message = f"Set {queryset[0].name} as {value}."
        else:
            message = f"Set {queryset.count()} VectorDatasets as {value}."
        messages.success(request, message)

    @admin.action(description="Make dataset public")
    def make_public(self, request, queryset):
        queryset.update(is_public=True)
        self.confirmation_message(request, queryset, "public")

    @admin.action(description="Make dataset private")
    def make_private(self, request, queryset):
        queryset.update(is_public=False)
        self.confirmation_message(request, queryset, "private")

    @admin.action(description="Publish dataset")
    def approve(self, request, queryset):
        queryset.update(is_approved=True)
        self.confirmation_message(request, queryset, "published")

    @admin.action(description="Unpublish dataset")
    def disapprove(self, request, queryset):
        queryset.update(is_approved=False)
        self.confirmation_message(request, queryset, "unpublished")

    def get_actions(self, request):
        actions = super().get_actions(request)

        if not request.user.is_superuser:
            for i in ["make_public", "make_private", "approve", "disapprove"]:
                del actions[i]
        return actions


@admin.register(VectorFile)
class VectorFileAdmin(PermissionBasedModelAdmin):
    list_display = ["id", "dataset", "created", "status"]
    fields = ["dataset", "file"]

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user

        super().save_model(request, obj, form, change)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "dataset":
            if request.user.is_superuser:
                kwargs["queryset"] = VectorDataset.objects.all()
            else:
                kwargs["queryset"] = VectorDataset.objects.filter(
                    created_by=request.user
                )

        elif db_field.name == "created_by":
            kwargs["initial"] = request.user.id

        return super().formfield_for_foreignkey(db_field, request, **kwargs)
