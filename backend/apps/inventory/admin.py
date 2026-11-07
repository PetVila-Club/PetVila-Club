from django import forms
from django.contrib import admin

from apps.core.admin_utils import ReadOnlyAdminMixin, form_action

from . import services
from .models import Lot, StockLevel, StockMovement


class ReceiveForm(forms.Form):
    quantity = forms.IntegerField(label="Quantidade recebida", min_value=1)
    lot_code = forms.CharField(label="Lote", required=False)
    expires_on = forms.DateField(label="Validade (AAAA-MM-DD)", required=False)
    storage = forms.CharField(label="Condições de armazenamento", required=False)


class AdjustForm(forms.Form):
    delta = forms.IntegerField(label="Ajuste (+/-)")
    reason = forms.CharField(label="Motivo", widget=forms.Textarea(attrs={"rows": 2}))


class QuarantineForm(forms.Form):
    quantity = forms.IntegerField(label="Quantidade inspecionada", min_value=1)
    approved = forms.BooleanField(label="Aprovado para voltar a vendável", required=False)
    reason = forms.CharField(label="Laudo / motivo", widget=forms.Textarea(attrs={"rows": 2}))


@admin.register(StockLevel)
class StockLevelAdmin(admin.ModelAdmin):
    list_display = ["sku", "physical", "reserved", "available_display", "damaged", "quarantine", "in_transit", "updated_at"]
    search_fields = ["sku__code", "sku__product__name"]
    readonly_fields = ["sku", "physical", "reserved", "damaged", "quarantine", "updated_at"]
    fields = ["sku", "physical", "reserved", "damaged", "quarantine", "in_transit", "updated_at"]
    actions = ["receive_action", "adjust_action", "quarantine_action"]

    def has_add_permission(self, request):
        return False

    @admin.display(description="disponível")
    def available_display(self, obj):
        return obj.available

    @form_action(form_class=ReceiveForm, title="Registrar entrada de mercadoria", success="Entrada registrada")
    def receive_action(self, request, obj, data):
        services.receive(obj.sku, data["quantity"], actor=request.user, lot_code=data["lot_code"],
                         expires_on=data["expires_on"], storage=data["storage"])

    @form_action(form_class=AdjustForm, title="Ajustar saldo (exige motivo)", success="Ajuste registrado")
    def adjust_action(self, request, obj, data):
        services.adjust(obj.sku, data["delta"], actor=request.user, reason=data["reason"])

    @form_action(form_class=QuarantineForm, title="Concluir inspeção de devolução", success="Inspeção registrada")
    def quarantine_action(self, request, obj, data):
        services.resolve_quarantine(obj.sku, data["quantity"], approved=data["approved"], actor=request.user, reason=data["reason"])


@admin.register(Lot)
class LotAdmin(admin.ModelAdmin):
    list_display = ["sku", "code", "expires_on", "quantity_remaining", "is_blocked"]
    list_filter = ["is_blocked"]
    search_fields = ["code", "sku__code"]
    list_editable = ["is_blocked"]
    readonly_fields = ["quantity_received", "quantity_remaining"]


@admin.register(StockMovement)
class StockMovementAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    list_display = ["created_at", "kind", "sku", "quantity", "lot", "actor", "reference_type", "reference_id", "reason"]
    list_filter = ["kind"]
    search_fields = ["sku__code", "reference_id", "idempotency_key"]
    date_hierarchy = "created_at"
