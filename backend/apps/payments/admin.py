import uuid

from django import forms
from django.contrib import admin

from apps.core.admin_utils import ReadOnlyAdminMixin, form_action, run_each
from apps.core.services import format_brl

from .models import Payment, PaymentEvent, Refund
from .services import reprocess_event, request_refund


class RefundForm(forms.Form):
    value = forms.DecimalField(label="Valor a estornar (R$)", min_value=0.01, decimal_places=2)
    reason = forms.CharField(label="Motivo", widget=forms.Textarea(attrs={"rows": 2}))


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ["external_id", "purpose", "user", "billing_type", "status", "value", "refunded", "due_date", "confirmed_at"]
    list_filter = ["status", "purpose", "billing_type"]
    search_fields = ["external_id", "external_subscription_id", "user__email"]
    readonly_fields = [f.name for f in Payment._meta.fields]
    actions = ["refund"]
    date_hierarchy = "created_at"

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.display(description="valor")
    def value(self, obj):
        return format_brl(obj.value_cents)

    @admin.display(description="estornado")
    def refunded(self, obj):
        return format_brl(obj.refunded_cents) if obj.refunded_cents else "—"

    @form_action(form_class=RefundForm, title="Estornar (financeiro, dentro da alçada)", success="Estorno executado")
    def refund(self, request, obj, data):
        cents = int(data["value"] * 100)
        # A chave inclui o envio do formulário: reenviar a mesma tela não duplica o estorno.
        key = f"admin:{obj.pk}:{cents}:{request.POST.get('csrfmiddlewaretoken', uuid.uuid4().hex)[:24]}"
        request_refund(obj, cents, actor=request.user, reason=data["reason"], key=key)


@admin.register(PaymentEvent)
class PaymentEventAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    list_display = ["received_at", "event_type", "payment_external_id", "result", "has_error"]
    list_filter = ["event_type", "result"]
    search_fields = ["external_event_id", "payment_external_id"]
    actions = ["reprocess"]

    def has_change_permission(self, request, obj=None):
        return obj is None

    @admin.display(boolean=True, description="erro")
    def has_error(self, obj):
        return bool(obj.error)

    @admin.action(description="Reprocessar eventos com erro")
    def reprocess(self, request, queryset):
        run_each(self, request, queryset.exclude(error=""), reprocess_event, "Eventos reprocessados")


@admin.register(Refund)
class RefundAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    list_display = ["created_at", "payment", "value_cents", "status", "requested_by", "reason"]
    list_filter = ["status"]
