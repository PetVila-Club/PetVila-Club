from django.contrib import admin

from apps.core.admin_utils import ReadOnlyAdminMixin, ReasonForm, form_action
from apps.core.services import format_brl

from .models import Order, OrderLine, ShippingZone
from .services import cancel_unpaid_order


class OrderLineInline(ReadOnlyAdminMixin, admin.TabularInline):
    model = OrderLine
    fields = ["sku_code", "product_name", "variant_name", "quantity", "list_price_cents", "unit_price_cents", "unit_cost_cents"]
    readonly_fields = fields
    extra = 0


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ["number", "user", "status", "total", "member_pricing", "billing_type", "created_at", "paid_at"]
    list_filter = ["status", "billing_type", "member_pricing"]
    search_fields = ["id", "user__email", "user__full_name"]
    readonly_fields = [f.name for f in Order._meta.fields]
    inlines = [OrderLineInline]
    actions = ["cancel"]
    date_hierarchy = "created_at"

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.display(description="total")
    def total(self, obj):
        return format_brl(obj.total_cents)

    @form_action(form_class=ReasonForm, title="Cancelar pedido não pago (libera reserva)", success="Pedido cancelado")
    def cancel(self, request, obj, data):
        from apps.core.exceptions import DomainError

        if not cancel_unpaid_order(obj.pk, reason=data["note"], actor=request.user):
            raise DomainError("Só pedidos aguardando pagamento podem ser cancelados aqui. Pagos exigem estorno.")


@admin.register(ShippingZone)
class ShippingZoneAdmin(admin.ModelAdmin):
    list_display = ["name", "cep_start", "cep_end", "price", "eta_days", "free_above_cents", "is_active"]
    list_editable = ["is_active"]

    @admin.display(description="frete")
    def price(self, obj):
        return format_brl(obj.price_cents)
