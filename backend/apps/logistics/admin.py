from django import forms
from django.contrib import admin

from apps.catalog.models import SKU
from apps.core.admin_utils import ReadOnlyAdminMixin, ReasonForm, form_action, run_each
from apps.fiscal.models import FiscalDocument

from . import services
from .models import Incident, Shipment, ShipmentLine


class CheckForm(forms.Form):
    counts = forms.CharField(
        label="Contagem conferida", widget=forms.Textarea(attrs={"rows": 6}),
        help_text="Uma linha por SKU no formato CODIGO=QUANTIDADE. Ex.: PV-SNK-001=2",
    )

    def clean_counts(self):
        result = {}
        for raw in self.cleaned_data["counts"].splitlines():
            raw = raw.strip()
            if not raw:
                continue
            if "=" not in raw:
                raise forms.ValidationError(f"Linha inválida: {raw}")
            code, qty = raw.split("=", 1)
            try:
                result[code.strip()] = result.get(code.strip(), 0) + int(qty)
            except ValueError as exc:
                raise forms.ValidationError(f"Quantidade inválida: {raw}") from exc
        return result


class LabelForm(forms.Form):
    carrier = forms.CharField(label="Transportador")
    service = forms.CharField(label="Serviço", required=False)
    tracking_code = forms.CharField(label="Código de rastreio (ou registro equivalente)")
    tracking_url = forms.URLField(label="Link de rastreio", required=False, assume_scheme="https")


class DeliveredForm(forms.Form):
    source = forms.ChoiceField(label="Entrega informada por", choices=[("carrier", "Transportador"), ("tutor", "Tutor"),
                                                                       ("operation", "Operação")])


class IncidentForm(forms.Form):
    kind = forms.ChoiceField(label="Tipo", choices=Incident.Kind.choices)
    source = forms.ChoiceField(label="Origem", choices=Incident.Source.choices)
    description = forms.CharField(label="Descrição", widget=forms.Textarea(attrs={"rows": 3}))


class ReturnForm(forms.Form):
    sku = forms.ModelChoiceField(label="SKU devolvido", queryset=SKU.objects.all())
    quantity = forms.IntegerField(label="Quantidade", min_value=1)
    reason = forms.CharField(label="Motivo", widget=forms.Textarea(attrs={"rows": 2}))


class ResendForm(forms.Form):
    items = forms.CharField(label="Itens do reenvio", widget=forms.Textarea(attrs={"rows": 4}),
                            help_text="Uma linha por SKU: CODIGO=QUANTIDADE")
    reason = forms.CharField(label="Motivo", widget=forms.Textarea(attrs={"rows": 2}))


class LineInline(ReadOnlyAdminMixin, admin.TabularInline):
    model = ShipmentLine
    fields = ["sku_code", "product_name", "quantity", "dog", "lot"]
    readonly_fields = fields
    extra = 0


class FiscalInline(admin.TabularInline):
    model = FiscalDocument
    fields = ["status", "document_type", "number", "series", "access_key", "file_url", "rejection_reason", "decision_note"]
    extra = 0
    can_delete = False


@admin.register(Shipment)
class ShipmentAdmin(admin.ModelAdmin):
    list_display = ["number", "kind", "status", "user", "reference", "tracking_code", "fiscal", "created_at"]
    list_filter = ["status", "kind"]
    search_fields = ["tracking_code", "user__email", "lines__sku_code"]
    readonly_fields = ["kind", "status", "user", "order", "cycle", "resend_of", "shipping_address", "divergences", "checked_by",
                       "label_registered_at", "shipped_at", "delivered_at", "delivery_source", "carrier", "service",
                       "tracking_code", "tracking_url", "picking_list"]
    inlines = [LineInline, FiscalInline]
    actions = ["start_picking", "check_action", "label", "ship", "delivered", "incident", "register_return"]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.display(description="referência")
    def reference(self, obj):
        return obj.cycle.code if obj.cycle_id else (obj.order.number if obj.order_id else "")

    @admin.display(description="fiscal")
    def fiscal(self, obj):
        ok, reason = services.fiscal_ok(obj)
        return "OK" if ok else reason

    @admin.display(description="lista de separação (por cão)")
    def picking_list(self, obj):
        from django.utils.html import format_html_join

        return format_html_join("", "<div>{} × {} · {} → {}</div>",
                                [(line.quantity, line.sku_code, line.product_name, line.dog.name if line.dog else "pedido")
                                 for line in obj.lines.select_related("dog")])

    def save_formset(self, request, form, formset, change):
        instances = formset.save(commit=False)
        for inst in instances:
            if isinstance(inst, FiscalDocument):
                inst.updated_by = request.user
            inst.save()
        formset.save_m2m()
        from apps.core.services import audit

        for inst in instances:
            audit(request.user, "fiscal_document_updated", inst, changes={"status": getattr(inst, "status", "")})

    @admin.action(description="Iniciar separação")
    def start_picking(self, request, queryset):
        run_each(self, request, queryset, lambda s: services.start_picking(s, actor=request.user), "Separação iniciada")

    @form_action(form_class=CheckForm, title="Conferir separação", success="Conferência registrada")
    def check_action(self, request, obj, data):
        divergences = services.check_shipment(obj, data["counts"], actor=request.user)
        if divergences:
            from apps.core.exceptions import DomainError

            raise DomainError("Divergências: " + "; ".join(f"{d['sku']} {d['kind']} (esperado {d['expected']}, contado {d['counted']})"
                                                         for d in divergences))

    @form_action(form_class=LabelForm, title="Registrar etiqueta e rastreio", success="Etiqueta registrada")
    def label(self, request, obj, data):
        services.register_label(obj, actor=request.user, **data)

    @admin.action(description="Expedir (baixa de estoque única)")
    def ship(self, request, queryset):
        run_each(self, request, queryset, lambda s: services.ship(s, actor=request.user), "Expedido")

    @form_action(form_class=DeliveredForm, title="Registrar entrega", success="Entrega registrada")
    def delivered(self, request, obj, data):
        services.mark_delivered(obj, actor=request.user, source=data["source"])

    @form_action(form_class=IncidentForm, title="Abrir ocorrência", success="Ocorrência aberta")
    def incident(self, request, obj, data):
        services.open_incident(obj, actor=request.user, **data)

    @form_action(form_class=ReturnForm, title="Registrar devolução (vai para inspeção)", success="Devolução registrada")
    def register_return(self, request, obj, data):
        services.register_return(obj, data["sku"], data["quantity"], actor=request.user, reason=data["reason"])


@admin.register(Incident)
class IncidentAdmin(admin.ModelAdmin):
    list_display = ["shipment", "kind", "source", "status", "resend", "created_at"]
    list_filter = ["status", "kind", "source"]
    readonly_fields = ["shipment", "kind", "source", "description", "resend", "created_by"]
    actions = ["resend_action", "resolve"]

    def has_add_permission(self, request):
        return False

    @form_action(form_class=ResendForm, title="Gerar reenvio vinculado", success="Reenvio criado")
    def resend_action(self, request, obj, data):
        from apps.core.exceptions import DomainError

        items = []
        for raw in data["items"].splitlines():
            if "=" not in raw:
                continue
            code, qty = raw.split("=", 1)
            sku = SKU.objects.filter(code=code.strip()).first()
            if sku is None:
                raise DomainError(f"SKU {code.strip()} não encontrado.")
            items.append((sku, int(qty)))
        services.create_resend(obj, items, actor=request.user, reason=data["reason"])

    @form_action(form_class=ReasonForm, title="Resolver ocorrência", success="Ocorrência resolvida")
    def resolve(self, request, obj, data):
        obj.status = Incident.Status.RESOLVED
        obj.resolution = data["note"]
        obj.save(update_fields=["status", "resolution", "updated_at"])
