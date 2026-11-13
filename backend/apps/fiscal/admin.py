from django.contrib import admin

from apps.core.services import audit

from .models import FiscalDocument


@admin.register(FiscalDocument)
class FiscalDocumentAdmin(admin.ModelAdmin):
    list_display = ["shipment", "status", "document_type", "number", "amount_cents", "procedure", "updated_at"]
    list_filter = ["status", "procedure"]
    search_fields = ["number", "access_key", "shipment__tracking_code"]
    readonly_fields = ["shipment", "updated_by", "created_at", "updated_at"]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)
        audit(request.user, "fiscal_document_updated", obj, reason=obj.rejection_reason or obj.decision_note,
              changes={"status": obj.status, "number": obj.number})
