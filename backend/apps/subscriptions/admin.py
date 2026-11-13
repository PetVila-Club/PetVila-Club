from django.contrib import admin

from apps.core.admin_utils import ReadOnlyAdminMixin, ReasonForm, form_action
from apps.core.services import format_brl

from . import services
from .models import Cycle, Subscription, SubscriptionEvent


class CycleInline(ReadOnlyAdminMixin, admin.TabularInline):
    model = Cycle
    fields = ["number", "status", "billing_date", "cutoff_date", "price_cents", "external_payment_id", "paid_at"]
    readonly_fields = fields
    extra = 0


class EventInline(ReadOnlyAdminMixin, admin.TabularInline):
    model = SubscriptionEvent
    fields = ["created_at", "kind", "actor", "detail"]
    readonly_fields = fields
    extra = 0


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ["number", "user", "kind", "plan", "dog", "status", "value", "next_billing_date", "cancel_effective_date"]
    list_filter = ["kind", "status", "plan", "billing_type"]
    search_fields = ["user__email", "user__full_name", "dog__name", "asaas_subscription_id"]
    readonly_fields = [f.name for f in Subscription._meta.fields]
    inlines = [CycleInline, EventInline]
    actions = ["cancel_action", "pause_action", "resume_action"]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.display(description="valor/ciclo")
    def value(self, obj):
        return format_brl(obj.total_per_cycle_cents)

    @form_action(form_class=ReasonForm, title="Cancelar assinatura (atendimento assistido)", success="Cancelamento registrado")
    def cancel_action(self, request, obj, data):
        services.cancel_subscription(obj, actor=request.user, reason=data["note"])

    @form_action(form_class=ReasonForm, title="Pausar assinatura", success="Assinatura pausada")
    def pause_action(self, request, obj, data):
        services.pause_subscription(obj, actor=request.user, reason=data["note"])

    @admin.action(description="Retomar assinatura pausada")
    def resume_action(self, request, queryset):
        from apps.core.admin_utils import run_each

        run_each(self, request, queryset, lambda o: services.resume_subscription(o, actor=request.user), "Assinatura retomada")


@admin.register(Cycle)
class CycleAdmin(admin.ModelAdmin):
    list_display = ["code", "subscription", "status", "billing_date", "cutoff_date", "paid_at"]
    list_filter = ["status", "subscription__kind", "subscription__plan"]
    search_fields = ["subscription__user__email", "external_payment_id", "subscription__dog__name"]
    readonly_fields = [f.name for f in Cycle._meta.fields]
    actions = ["generate_kits"]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.action(description="Gerar sugestão de kit (ciclos pagos)")
    def generate_kits(self, request, queryset):
        from apps.core.admin_utils import run_each
        from apps.curation.services import generate_kit

        run_each(self, request, queryset, lambda c: generate_kit(c, actor=request.user), "Sugestões geradas")
