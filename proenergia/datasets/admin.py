import re

from django.contrib import admin, messages
from django.forms import CheckboxSelectMultiple, ModelForm
from django.utils.translation import gettext_lazy as _
from django.utils.translation import ngettext
from django_json_widget.widgets import JSONEditorWidget
from unfold.admin import ModelAdmin

from proenergia.datasets.tasks import (
    generate_pmtiles,
    generate_scenario_pmtiles,
    import_scenario_data_csv,
)

from .models import (
    DataModel,
    Scenario,
    ScenarioFile,
    VectorDataset,
    VectorFile,
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


@admin.register(VectorDataset)
class VectorDatasetAdmin(PermissionBasedModelAdmin):
    list_display = ["name", "updated", "is_public", "is_approved"]
    fields = ["name", "description", "source"]
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

    @admin.action(description=_("Publish dataset"))
    def approve(self, request, queryset):
        queryset.update(is_approved=True)
        self.confirmation_message(request, queryset, _("published"))

    @admin.action(description=_("Unpublish dataset"))
    def disapprove(self, request, queryset):
        queryset.update(is_approved=False)
        self.confirmation_message(request, queryset, _("unpublished"))

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
            "filter_fields",
            "popup_fields",
            "summary_fields",
            "visualization_column",
            "color_coding",
            "contextual_layers",
        ]
        widgets = {
            "contextual_layers": CheckboxSelectMultiple(),
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
class DataModelAdmin(ModelAdmin):
    form = DataModelAdminForm

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        if db_field.name == "contextual_layers":
            kwargs["queryset"] = VectorDataset.objects.filter(
                is_approved=True, files__status="ready"
            ).distinct()
        return super().formfield_for_manytomany(db_field, request, **kwargs)


@admin.register(Scenario)
class ScenarioAdmin(ModelAdmin):
    list_display = ["name", "model"]
    fields = ["name", "model", "vector_dataset"]


@admin.register(ScenarioFile)
class ScenarioFileAdmin(ModelAdmin):
    list_display = ["id", "scenario", "created", "status"]
    fields = ["scenario", "file", "status", "error_message"]
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
            import_scenario_data_csv.delay(obj.id)

        if files.count():
            messages.success(
                request,
                ngettext(
                    "{%(count)d file queued for reprocessing.",
                    "{%(count)d files queued for reprocessing.",
                    files.count(),
                )
                % {"count": files.count()},
            )
        else:
            messages.error(
                request,
                _("Files in created or processing state cannot be reprocessed."),
            )
