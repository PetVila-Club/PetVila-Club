from django import forms
from django.contrib import admin, messages
from django.utils.html import format_html_join

from apps.core.admin_utils import OptionalReasonForm, ReasonForm, form_action, run_each
from apps.core.services import format_brl

from . import services
from .models import CompositionLine, CompositionVersion, KitModel, OfferVersion, Plan


class PublishForm(forms.Form):
    valid_from = forms.DateTimeField(label="Vigência a partir de (vazio = agora)", required=False,
                                     help_text="Formato: AAAA-MM-DD HH:MM")


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ["name", "code", "base_item_count", "current_price", "current_composition_total", "is_active"]
    prepopulated_fields = {"code": ["name"]}

    @admin.display(description="preço publicado")
    def current_price(self, obj):
        offer = obj.current_offer()
        return format_brl(offer.price_cents) if offer else "Pendente (não publicado)"

    @admin.display(description="itens na composição vigente")
    def current_composition_total(self, obj):
        comp = obj.current_composition()
        return comp.total_items if comp else "—"


@admin.register(OfferVersion)
class OfferVersionAdmin(admin.ModelAdmin):
    list_display = ["plan", "version", "status", "price", "valid_from", "valid_until", "approved_by", "published_by"]
    list_filter = ["plan", "status"]
    readonly_fields = ["status", "approved_by", "approved_at", "approval_note", "published_by", "published_at",
                       "valid_until", "billing_cycle"]
    actions = ["approve", "publish", "archive"]
    fieldsets = (
        (None, {"fields": ("plan", "version", "status")}),
        ("Condição comercial", {"fields": ("price_cents", "billing_cycle", "commitment_options", "shipping_cents", "benefits", "terms")}),
        ("Vigência", {"fields": ("valid_from", "valid_until")}),
        ("Aprovação", {"fields": ("approved_by", "approved_at", "approval_note", "published_by", "published_at")}),
        ("Interno", {"fields": ("internal_notes",)}),
    )

    @admin.display(description="preço")
    def price(self, obj):
        return format_brl(obj.price_cents) if obj.price_cents else "Pendente"

    def get_changeform_initial_data(self, request):
        initial = super().get_changeform_initial_data(request)
        plan_id = request.GET.get("plan")
        if plan_id:
            plan = Plan.objects.filter(pk=plan_id).first()
            if plan:
                initial["version"] = services.next_offer_version(plan)
        return initial

    def has_change_permission(self, request, obj=None):
        # Oferta aprovada/publicada é imutável: mudanças viram nova versão (COM-02).
        if obj is not None and obj.status != OfferVersion.Status.DRAFT:
            return False
        return super().has_change_permission(request, obj)

    @form_action(form_class=ReasonForm, title="Aprovar oferta (gestor)",
                 description="Registre quem aprovou o preço e em qual instância. Oferta sem preço não pode ser aprovada.",
                 success="Oferta aprovada")
    def approve(self, request, obj, data):
        services.approve_offer(obj, request.user, data["note"])

    @form_action(form_class=PublishForm, title="Publicar oferta (gestor)", success="Oferta publicada")
    def publish(self, request, obj, data):
        services.publish_offer(obj, request.user, data["valid_from"])

    @form_action(form_class=ReasonForm, title="Arquivar oferta", success="Oferta arquivada")
    def archive(self, request, obj, data):
        services.archive_offer(obj, request.user, data["note"])


class CompositionLineInline(admin.TabularInline):
    model = CompositionLine
    extra = 0

    def has_change_permission(self, request, obj=None):
        return obj is None or obj.status == CompositionVersion.Status.DRAFT

    has_add_permission = has_change_permission
    has_delete_permission = has_change_permission


@admin.register(CompositionVersion)
class CompositionVersionAdmin(admin.ModelAdmin):
    list_display = ["plan", "version", "status", "total", "valid_from", "approved_by", "published_by"]
    list_filter = ["plan", "status"]
    inlines = [CompositionLineInline]
    readonly_fields = ["status", "created_by", "approved_by", "approved_at", "published_by", "published_at", "previous",
                       "validation", "diff"]
    actions = ["submit", "approve", "publish", "clone"]

    @admin.display(description="total de itens")
    def total(self, obj):
        return f"{obj.total_items} / base {obj.plan.base_item_count}"

    @admin.display(description="validação")
    def validation(self, obj):
        if not obj.pk:
            return "Salve para validar."
        errors, warnings = services.validate_composition(obj)
        rows = [("❌ " + e,) for e in errors] + [("⚠️ " + w,) for w in warnings]
        return format_html_join("", "<div>{}</div>", rows) if rows else "✅ Sem erros."

    @admin.display(description="diferenças em relação à vigente")
    def diff(self, obj):
        if not obj.pk:
            return "—"
        current = obj.plan.current_composition()
        if current is None or current.pk == obj.pk:
            current = obj.previous
        rows = services.diff_compositions(obj, current)
        if not rows:
            return "Sem diferenças de quantidade."
        return format_html_join("", "<div>{}: {} → {}</div>", [(r["category"], r["before"], r["after"]) for r in rows])

    def has_change_permission(self, request, obj=None):
        if obj is not None and obj.status != CompositionVersion.Status.DRAFT:
            return False
        return super().has_change_permission(request, obj)

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    @admin.action(description="Enviar para revisão")
    def submit(self, request, queryset):
        run_each(self, request, queryset, lambda o: services.submit_composition(o, request.user), "Enviada para revisão")

    @admin.action(description="Aprovar adequação (curador)")
    def approve(self, request, queryset):
        run_each(self, request, queryset, lambda o: services.approve_composition(o, request.user), "Composição aprovada")

    @form_action(form_class=PublishForm, title="Publicar composição (gestor)",
                 description="Ciclos já fechados não mudam. A nova versão vale para ciclos curados a partir da vigência.",
                 success="Composição publicada")
    def publish(self, request, obj, data):
        services.publish_composition(obj, request.user, data["valid_from"])

    @admin.action(description="Criar novo rascunho a partir desta versão")
    def clone(self, request, queryset):
        for obj in queryset:
            draft = services.clone_composition(obj, request.user)
            self.message_user(request, f"Rascunho v{draft.version} criado para {obj.plan.name}.", messages.SUCCESS)


@admin.register(KitModel)
class KitModelAdmin(admin.ModelAdmin):
    list_display = ["name", "plan", "status", "sku_count"]
    list_filter = ["plan", "status"]
    filter_horizontal = ["skus"]
    actions = ["archive"]

    @admin.display(description="SKUs elegíveis")
    def sku_count(self, obj):
        return obj.skus.count() or "todos da categoria"

    @form_action(form_class=OptionalReasonForm, title="Arquivar modelo (histórico preservado)", success="Modelo arquivado")
    def archive(self, request, obj, data):
        obj.status = KitModel.Status.ARCHIVED
        obj.save(update_fields=["status", "updated_at"])
