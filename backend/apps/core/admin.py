from django.contrib import admin

from .admin_utils import ReadOnlyAdminMixin
from .models import AuditLog, OperationalAlert, OperationalSetting
from .services import audit, format_brl

_original_index = admin.site.index


def index_with_metrics(request, extra_context=None):
    from .ops import compute_metrics

    extra_context = extra_context or {}
    try:
        metrics = compute_metrics()
        extra_context.update(pv_metrics=metrics, pv_mrr=format_brl(metrics["mrr_cents"]))
    except Exception:  # o painel nunca deve cair por causa dos indicadores
        pass
    return _original_index(request, extra_context)


admin.site.index = index_with_metrics


@admin.register(OperationalSetting)
class OperationalSettingAdmin(admin.ModelAdmin):
    list_display = ["key", "value", "description", "updated_at"]
    readonly_fields = ["updated_at"]

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        audit(request.user, "setting_changed", obj, changes={"value": obj.value})


@admin.register(AuditLog)
class AuditLogAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    list_display = ["created_at", "actor", "action", "object_type", "object_id", "object_repr"]
    list_filter = ["action", "object_type"]
    search_fields = ["object_id", "object_repr", "actor__email", "reason"]
    date_hierarchy = "created_at"


@admin.register(OperationalAlert)
class OperationalAlertAdmin(admin.ModelAdmin):
    list_display = ["title", "kind", "status", "assigned_to", "due_at", "created_at"]
    list_filter = ["status", "kind"]
    search_fields = ["title", "detail", "object_id"]
    list_editable = ["status", "assigned_to"]
    readonly_fields = ["kind", "title", "detail", "object_type", "object_id", "dedupe_key", "created_at", "updated_at"]

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        audit(request.user, "alert_updated", obj, reason=obj.resolution, changes={"status": obj.status})
