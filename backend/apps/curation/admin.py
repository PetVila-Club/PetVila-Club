import json

from django import forms
from django.contrib import admin, messages
from django.utils.html import format_html, format_html_join

from apps.catalog.models import SKU
from apps.core.admin_utils import OptionalReasonForm, ReadOnlyAdminMixin, ReasonForm, form_action, run_each

from . import services
from .models import CycleKit, KitLine


class SubstituteForm(forms.Form):
    new_sku = forms.ModelChoiceField(label="Novo SKU (mesma categoria)", queryset=SKU.objects.filter(is_active=True).select_related("product"))
    justification = forms.CharField(label="Justificativa", widget=forms.Textarea(attrs={"rows": 3}))


class KitLineInline(admin.TabularInline):
    model = KitLine
    fields = ["category", "sku", "quantity", "status", "replaces", "justification", "decided_by", "compat"]
    readonly_fields = fields
    extra = 0
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False

    @admin.display(description="compatibilidade")
    def compat(self, obj):
        from .engine import check_compatibility

        result = check_compatibility(obj.sku, obj.kit.profile_version.data)
        return "✅" if result.status == "ok" else f"⚠️ {result.reason}"


@admin.register(CycleKit)
class CycleKitAdmin(admin.ModelAdmin):
    list_display = ["__str__", "status", "group_key", "kit_model", "review_summary", "approved_by", "closed_at"]
    list_filter = ["status", "cycle__subscription__plan", "group_key"]
    search_fields = ["dog__name", "dog__tutor__email", "cycle__external_payment_id"]
    readonly_fields = ["cycle", "dog", "status", "group_key", "profile_version", "profile", "composition", "kit_model",
                       "engine_version", "review_reasons_view", "trace_view", "approved_by", "approved_at", "closed_at",
                       "decision_note", "snapshot_view"]
    exclude = ["trace", "snapshot", "review_reasons"]
    inlines = [KitLineInline]
    actions = ["generate_pending", "approve", "reject", "close", "regenerate"]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.display(description="exceções")
    def review_summary(self, obj):
        return f"{len(obj.review_reasons)} pendência(s)" if obj.review_reasons else "—"

    @admin.display(description="perfil usado")
    def profile(self, obj):
        data = obj.profile_version.data
        return format_html("<b>{}</b> · porte {} · {} kg<br>Restrições: {}<br>Preferências: {}", data.get("name"),
                           data.get("size") or "?", data.get("weight_kg") or "?",
                           ", ".join(data.get("restrictions") or []) or "nenhuma",
                           ", ".join(data.get("preferences") or []) or "nenhuma")

    @admin.display(description="motivos de revisão")
    def review_reasons_view(self, obj):
        if not obj.review_reasons:
            return "Nenhum"
        return format_html_join("", "<div>⚠️ {}</div>", [(r,) for r in obj.review_reasons])

    @admin.display(description="simulação: regras, candidatos e rejeitados")
    def trace_view(self, obj):
        rows = []
        for cat in obj.trace.get("categories", []):
            chosen = ", ".join(f"{c['sku']} ×{c['chosen_units']} ({c['score']:+d})" for c in cat["candidates"] if c["chosen_units"])
            others = ", ".join(f"{c['sku']} ({c['score']:+d})" for c in cat["candidates"] if not c["chosen_units"])
            rejected = "; ".join(f"{r['sku']}: {r['reason']}" for r in cat["rejected"])
            rows.append((cat["category"], cat["quantity"], chosen or "—", others or "—", rejected or "—"))
        table = format_html_join(
            "", "<tr><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>", rows,
        )
        return format_html(
            "<p>Regras {} · pesos {}</p><table><tr><th>Categoria</th><th>Qtd</th><th>Escolhidos</th><th>Outros elegíveis</th>"
            "<th>Rejeitados e motivo</th></tr>{}</table>",
            obj.engine_version, json.dumps(obj.trace.get("weights", {})), table,
        )

    @admin.display(description="cópia congelada no fechamento")
    def snapshot_view(self, obj):
        if not obj.snapshot:
            return "Ainda não fechado."
        return format_html("<pre style='white-space:pre-wrap'>{}</pre>", json.dumps(obj.snapshot, ensure_ascii=False, indent=2))

    @admin.action(description="Gerar sugestões para todos os ciclos pagos")
    def generate_pending(self, request, queryset):
        result = services.generate_pending_kits(actor=request.user)
        self.message_user(request, f"{result['created']} sugestão(ões) gerada(s).", messages.SUCCESS)
        for failure in result["failed"]:
            self.message_user(request, failure, messages.WARNING)

    @form_action(form_class=OptionalReasonForm, title="Aprovar kit (curador)",
                 description="Kits com exceção exigem justificativa. Itens incompatíveis ou com cadastro incompleto bloqueiam.",
                 success="Kit aprovado")
    def approve(self, request, obj, data):
        services.approve_kit(obj, actor=request.user, note=data["note"])

    @form_action(form_class=ReasonForm, title="Rejeitar sugestão", success="Sugestão rejeitada")
    def reject(self, request, obj, data):
        services.reject_kit(obj, actor=request.user, note=data["note"])

    @admin.action(description="Fechar conteúdo e reservar estoque")
    def close(self, request, queryset):
        run_each(self, request, queryset, lambda k: services.close_kit(k, actor=request.user), "Kit fechado e reservado")

    @form_action(form_class=ReasonForm, title="Reprocessar sugestão (substitui a atual)",
                 description="Impacto: as linhas sugeridas atuais serão descartadas e recalculadas. Kits aprovados ou fechados não são afetados.",
                 success="Sugestão reprocessada")
    def regenerate(self, request, obj, data):
        services.generate_kit(obj.cycle, actor=request.user, regenerate=True)


@admin.register(KitLine)
class KitLineAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    list_display = ["kit", "category", "sku", "quantity", "status", "replaces", "decided_by"]
    list_filter = ["status", "category"]
    search_fields = ["sku__code", "kit__dog__name"]
    actions = ["substitute"]

    def has_change_permission(self, request, obj=None):
        return obj is None

    @form_action(form_class=SubstituteForm, title="Substituir SKU da linha",
                 description="Mesma categoria e quantidade; o substituto precisa ser compatível com o perfil do cão.",
                 success="Linha substituída")
    def substitute(self, request, obj, data):
        services.substitute_line(obj, data["new_sku"], actor=request.user, justification=data["justification"])
