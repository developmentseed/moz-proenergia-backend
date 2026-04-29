import re

from django.contrib import admin, messages
from django.contrib.admin import helpers
from django.contrib.admin.decorators import display
from django.forms import CheckboxSelectMultiple, ModelForm
from django.template.response import TemplateResponse
from django.utils.translation import gettext as _
from django.utils.translation import ngettext
from django_json_widget.widgets import JSONEditorWidget
from modeltranslation.admin import TabbedTranslationAdmin
from unfold.admin import ModelAdmin

from proenergia.datasets.tasks import (
    delete_item,
    generate_pmtiles,
    generate_scenario_pmtiles,
)

from .models import (
    DataModel,
    RasterDataset,
    RasterFile,
    ReferenceDataset,
    ReferenceFile,
    Scenario,
    ScenarioFile,
    VectorDataset,
    VectorFile,
)


def _async_delete_action(model_admin, request, queryset, model_name):
    if request.POST.get("post"):
        count = queryset.count()
        for item in queryset:
            delete_item.delay(model_name, item.id)
        messages.success(
            request,
            ngettext(
                "%(count)d item queued for deletion.",
                "%(count)d items queued for deletion.",
                count,
            )
            % {"count": count},
        )
        return None

    opts = model_admin.model._meta
    context = {
        **model_admin.admin_site.each_context(request),
        "title": _("Are you sure?"),
        "objects_name": str(opts.verbose_name_plural),
        "queryset": queryset,
        "opts": opts,
        "action_checkbox_name": helpers.ACTION_CHECKBOX_NAME,
        "media": model_admin.media,
    }
    return TemplateResponse(
        request,
        "admin/datasets/async_delete_confirmation.html",
        context,
    )


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


@admin.register(RasterDataset)
@admin.register(VectorDataset)
@admin.register(ReferenceDataset)
class VectorDatasetAdmin(PermissionBasedModelAdmin, TabbedTranslationAdmin):
    list_display = ["name", "updated", "is_public", "is_approved"]
    fields = [
        "name",
        "description",
        "source",
        "contact",
        "published",
        "temporal_extent",
        "crs",
        "frequency",
        "lineage",
        "license",
        "attribute",
    ]
    actions = ["make_public", "make_private", "approve", "disapprove"]

    def get_fields(self, request, obj=None):
        fields = super().get_fields(request, obj)
        if request.user.is_superuser:
            return fields + ["is_public", "is_approved"]
        return fields

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

    @admin.action(description=_("Make dataset public"))
    def make_public(self, request, queryset):
        queryset.update(is_public=True)
        self.confirmation_message(request, queryset, _("public"))

    @admin.action(description=_("Make dataset private"))
    def make_private(self, request, queryset):
        queryset.update(is_public=False)
        self.confirmation_message(request, queryset, _("private"))

    @admin.action(description=_("Approve dataset"))
    def approve(self, request, queryset):
        queryset.update(is_approved=True)
        self.confirmation_message(request, queryset, _("approved"))

    @admin.action(description=_("Set as not approved"))
    def disapprove(self, request, queryset):
        queryset.update(is_approved=False)
        self.confirmation_message(request, queryset, _("not approved"))

    def get_actions(self, request):
        actions = super().get_actions(request)

        if not request.user.is_superuser:
            for i in ["make_public", "make_private", "approve", "disapprove"]:
                del actions[i]
        return actions


@admin.register(VectorFile)
class VectorFileAdmin(PermissionBasedModelAdmin):
    list_display = ["id", "dataset", "created", "status"]
    fields = ["dataset", "file", "status", "error_message"]
    readonly_fields = ["error_message", "status"]
    list_filter = ["dataset", "status"]
    actions = ["reprocess_files"]

    def get_fields(self, request, obj=None):
        fields = super().get_fields(request, obj)
        # Hide error_message and status in add form (when obj is None) or status is not error
        if obj is None:
            return [f for f in fields if f not in ["error_message", "status"]]
        if obj and obj.status != "error":
            return [f for f in fields if f != "error_message"]
        return fields

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

    def has_change_permission(self, request, obj=None):
        return False

    @admin.action(description=_("Reprocess files"))
    def reprocess_files(self, request, queryset):
        files = queryset.filter(status__in=["error", "ready"])

        for obj in files:
            generate_pmtiles.delay(obj.id)

        if files.count():
            messages.success(
                request,
                ngettext(
                    "%(count)d file queued for reprocessing.",
                    "%(count)d files queued for reprocessing.",
                    files.count(),
                )
                % {"count": files.count()},
            )
        else:
            messages.error(
                request,
                _("Files in created or processing state cannot be reprocessed."),
            )


class DataModelAdminForm(ModelForm):
    class Meta:
        model = DataModel
        fields = [
            "name",
            "description",
            "presentation_order",
            "filter_fields",
            "popup_fields",
            "summary_fields",
            "visualization_column",
            "color_coding",
            "contextual_layers",
            "raster_layers",
            "reference_datasets",
            "is_public",
        ]
        widgets = {
            "contextual_layers": CheckboxSelectMultiple(),
            "raster_layers": CheckboxSelectMultiple(),
            "reference_datasets": CheckboxSelectMultiple(),
            "filter_fields": JSONEditorWidget(
                height="400px",
                width="90%",
                options={
                    "mode": "tree",
                    "modes": ["tree", "form", "view", "code", "text"],
                    "search": True,
                },
            ),
            "popup_fields": JSONEditorWidget(
                height="400px",
                width="90%",
                options={
                    "mode": "tree",
                    "modes": ["tree", "form", "view", "code", "text"],
                    "search": True,
                },
            ),
            "summary_fields": JSONEditorWidget(
                height="400px",
                width="90%",
                options={
                    "mode": "tree",
                    "modes": ["tree", "form", "view", "code", "text"],
                    "search": True,
                },
            ),
            "color_coding": JSONEditorWidget(
                height="400px",
                width="90%",
                options={
                    "mode": "tree",
                    "modes": ["tree", "form", "view", "code", "text"],
                    "search": True,
                },
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filter contextual_layers to only show approved datasets with ready files
        self.fields["contextual_layers"].queryset = VectorDataset.objects.filter(
            is_approved=True, files__status="ready"
        ).distinct()

    def clean(self):
        cleaned_data = super().clean()
        filter_fields = cleaned_data.get("filter_fields")
        popup_fields = cleaned_data.get("popup_fields")
        summary_fields = cleaned_data.get("summary_fields")
        color_coding = cleaned_data.get("color_coding")

        if filter_fields:
            if type(filter_fields) is not list:
                self.add_error("filter_fields", _("Content should be a list."))
            else:
                for i in enumerate(filter_fields):
                    keys = i[1].keys()
                    if (
                        "label" not in keys
                        or "description" not in keys
                        or "column" not in keys
                    ):
                        self.add_error("filter_fields", _("Missing a required key."))

        if popup_fields:
            if type(popup_fields) is not list:
                self.add_error("popup_fields", _("Content should be a list"))
            else:
                for i in enumerate(popup_fields):
                    keys = i[1].keys()
                    if (
                        "label" not in keys
                        or "description" not in keys
                        or "column" not in keys
                    ):
                        self.add_error("popup_fields", _("Missing a required key."))

        if summary_fields:
            if type(summary_fields) is not list:
                self.add_error("summary_fields", _("Content should be a list"))
            else:
                for i in enumerate(summary_fields):
                    keys = i[1].keys()
                    if (
                        "label" not in keys
                        or "description" not in keys
                        or "columns" not in keys
                    ):
                        self.add_error("summary_fields", _("Missing a required key."))
                    else:
                        if type(i[1].get("columns")) is not list:
                            self.add_error(
                                "summary_fields",
                                _("The value for the columns key should be a list."),
                            )

                    if "method" in keys and i[1].get("method") not in [
                        "sum",
                        "average",
                        "count",
                        "min",
                        "max",
                    ]:
                        self.add_error(
                            "summary_fields",
                            _(
                                "The value for the methods key should be sum, count, average, min or max."
                            ),
                        )

                    if "chartType" in keys and i[1].get("chartType") not in [
                        "bar",
                        "donut",
                        "stacked",
                        "column",
                        "area",
                        "highlight",
                    ]:
                        self.add_error(
                            "summary_fields",
                            _(
                                "The value for the chartType key should be bar, donut, stacked, column, area or highlight."
                            ),
                        )

                    if "hasDecimal" in keys and i[1].get("hasDecimal") not in [
                        True,
                        False,
                    ]:
                        self.add_error(
                            "summary_fields",
                            _(
                                "The value for the hasDecimal key should be true or false. If not specified, it's assumed to be false."
                            ),
                        )

        if color_coding:
            if type(color_coding) is not list:
                self.add_error("color_coding", _("Content should be a list"))
            else:
                for i in enumerate(color_coding):
                    keys = i[1].keys()
                    if "value" not in keys or "color" not in keys:
                        self.add_error("color_coding", _("Missing a required key."))

                    regex = re.compile(
                        r"^#?(?:[0-9a-fA-F]{6}|[0-9a-fA-F]{3})$", re.IGNORECASE
                    )
                    if i[1].get("color") and regex.match(i[1].get("color")) is None:
                        self.add_error(
                            "color_coding",
                            _(
                                "The value for the color key should be a valid hex color code."
                            ),
                        )


@admin.register(DataModel)
class DataModelAdmin(ModelAdmin, TabbedTranslationAdmin):
    list_display = ["name", "presentation_order", "is_public"]
    list_editable = ["presentation_order"]
    form = DataModelAdminForm
    actions = ["async_delete"]

    @admin.action(description=_("Delete selected Data Models"), permissions=["delete"])
    def async_delete(self, request, queryset):
        return _async_delete_action(
            model_admin=self,
            request=request,
            queryset=queryset,
            model_name="DataModel",
        )

    def delete_model(self, request, instance):
        delete_item.delay("DataModel", instance.id)

        messages.success(request, _(f"{instance.name} was queued for deletion."))

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        if db_field.name == "contextual_layers":
            kwargs["queryset"] = VectorDataset.objects.filter(
                is_approved=True, files__status="ready"
            ).distinct()
        if db_field.name == "raster_layers":
            kwargs["queryset"] = RasterDataset.objects.filter(
                is_approved=True
            ).distinct()
        if db_field.name == "reference_datasets":
            kwargs["queryset"] = ReferenceDataset.objects.filter(
                is_approved=True
            ).distinct()
        return super().formfield_for_manytomany(db_field, request, **kwargs)

    def get_actions(self, request):
        actions = super().get_actions(request)
        if "delete_selected" in actions:
            del actions["delete_selected"]
        return actions


@admin.register(Scenario)
class ScenarioAdmin(ModelAdmin, TabbedTranslationAdmin):
    list_display = ["name", "model", "presentation_order"]
    list_editable = ["presentation_order"]
    list_filter = ["model"]
    fields = ["name", "model", "vector_dataset", "presentation_order"]
    actions = ["async_delete"]

    @admin.action(description=_("Delete selected Scenarios"), permissions=["delete"])
    def async_delete(self, request, queryset):
        return _async_delete_action(
            model_admin=self,
            request=request,
            queryset=queryset,
            model_name="Scenario",
        )

    def delete_model(self, request, instance):
        delete_item.delay("Scenario", instance.id)
        # for item in queryset:

        messages.success(request, _(f"{instance.name} was queued for deletion."))

    def get_actions(self, request):
        actions = super().get_actions(request)
        if "delete_selected" in actions:
            del actions["delete_selected"]
        return actions


@admin.register(ScenarioFile)
class ScenarioFileAdmin(ModelAdmin):
    @display(
        boolean=True,
        description=_("Is active"),
    )
    def is_active(self, obj):
        return obj.scenario.latest_file() == obj

    list_display = ["id", "scenario", "created", "status", "is_active"]
    fields = ["scenario", "file", "low_zoom_as_points", "status", "error_message"]
    readonly_fields = ["status", "error_message"]
    list_filter = ["scenario", "status"]
    actions = ["reprocess_files"]

    def get_fields(self, request, obj=None):
        fields = super().get_fields(request, obj)
        # Hide error_message and status in add form (when obj is None) or status is not error
        if obj is None:
            return [f for f in fields if f not in ["error_message", "status"]]
        if obj and obj.status != "error":
            return [f for f in fields if f != "error_message"]
        return fields

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user

        obj.last_updated_by = request.user
        super().save_model(request, obj, form, change)

    def has_change_permission(self, request, obj=None):
        return False

    @admin.action(description=_("Reprocess files"))
    def reprocess_files(self, request, queryset):
        files = queryset.filter(status__in=["error", "ready"])

        for obj in files:
            generate_scenario_pmtiles.delay(obj.id)

        if files.count():
            messages.success(
                request,
                ngettext(
                    "%(count)d file queued for reprocessing.",
                    "%(count)d files queued for reprocessing.",
                    files.count(),
                )
                % {"count": files.count()},
            )
        else:
            messages.error(
                request,
                _("Files in created or processing state cannot be reprocessed."),
            )


@admin.register(RasterFile)
class RasterFileAdmin(PermissionBasedModelAdmin):
    list_display = ["id", "dataset", "created", "created_by"]
    fields = ["dataset", "file"]
    readonly_fields = ["created", "created_by"]
    list_filter = ["created_by", "dataset"]

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user

        super().save_model(request, obj, form, change)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "dataset":
            if request.user.is_superuser:
                kwargs["queryset"] = RasterDataset.objects.all()
            else:
                kwargs["queryset"] = RasterDataset.objects.filter(
                    created_by=request.user
                )

        elif db_field.name == "created_by":
            kwargs["initial"] = request.user.id

        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(ReferenceFile)
class ReferenceFileAdmin(PermissionBasedModelAdmin):
    list_display = ["id", "dataset", "created", "created_by"]
    fields = ["dataset", "file"]
    readonly_fields = ["created", "created_by"]
    list_filter = ["created_by", "dataset"]

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user

        super().save_model(request, obj, form, change)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "dataset":
            if request.user.is_superuser:
                kwargs["queryset"] = ReferenceDataset.objects.all()
            else:
                kwargs["queryset"] = ReferenceDataset.objects.filter(
                    created_by=request.user
                )

        elif db_field.name == "created_by":
            kwargs["initial"] = request.user.id

        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def has_change_permission(self, request, obj=None):
        return False
