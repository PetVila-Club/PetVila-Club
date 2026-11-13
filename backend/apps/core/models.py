from django.conf import settings
from django.db import models


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField("criado em", auto_now_add=True)
    updated_at = models.DateTimeField("atualizado em", auto_now=True)

    class Meta:
        abstract = True


class OperationalSetting(models.Model):
    """Parâmetros operacionais editáveis no painel (limites, prazos, janelas)."""

    key = models.SlugField("chave", max_length=80, unique=True)
    value = models.JSONField("valor")
    description = models.CharField("descrição", max_length=255, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "parâmetro operacional"
        verbose_name_plural = "parâmetros operacionais"
        ordering = ["key"]

    def __str__(self):
        return f"{self.key} = {self.value}"


class AuditLog(models.Model):
    """ADM-02: ator, data, objeto, ação, motivo e diferenças relevantes."""

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name="ator", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="+",
    )
    action = models.CharField("ação", max_length=80)
    object_type = models.CharField("objeto", max_length=80)
    object_id = models.CharField("ID do objeto", max_length=64)
    object_repr = models.CharField("descrição do objeto", max_length=255, blank=True)
    reason = models.TextField("motivo", blank=True)
    changes = models.JSONField("diferenças", default=dict, blank=True)
    created_at = models.DateTimeField("data", auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "registro de auditoria"
        verbose_name_plural = "auditoria"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["object_type", "object_id"])]

    def __str__(self):
        return f"{self.created_at:%d/%m/%Y %H:%M} · {self.action} · {self.object_type}#{self.object_id}"


class OperationalAlert(TimeStampedModel):
    """Fila de exceções da operação: cada uma com responsável, prazo e solução registrada."""

    class Kind(models.TextChoices):
        RECONCILIATION = "reconciliation", "Divergência financeira"
        PAYMENT = "payment", "Pagamento"
        PROFILE_CHANGED = "profile_changed", "Perfil alterado após fechamento"
        STOCKOUT = "stockout", "Ruptura de estoque"
        CURATION = "curation", "Curadoria bloqueada"
        FISCAL = "fiscal", "Documento fiscal"
        LOGISTICS = "logistics", "Expedição/entrega"
        INTEGRATION = "integration", "Falha de integração"
        FEEDBACK = "feedback", "Feedback negativo"

    class Status(models.TextChoices):
        OPEN = "open", "Aberto"
        IN_PROGRESS = "in_progress", "Em tratamento"
        RESOLVED = "resolved", "Resolvido"

    kind = models.CharField("tipo", max_length=30, choices=Kind.choices)
    status = models.CharField("situação", max_length=20, choices=Status.choices, default=Status.OPEN)
    title = models.CharField("título", max_length=200)
    detail = models.TextField("detalhe", blank=True)
    object_type = models.CharField("objeto", max_length=80, blank=True)
    object_id = models.CharField("ID do objeto", max_length=64, blank=True)
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name="responsável", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="+",
    )
    due_at = models.DateTimeField("prazo", null=True, blank=True)
    resolution = models.TextField("solução registrada", blank=True)
    dedupe_key = models.CharField(max_length=160, unique=True, null=True, blank=True)

    class Meta:
        verbose_name = "alerta operacional"
        verbose_name_plural = "alertas operacionais"
        ordering = ["status", "-created_at"]

    def __str__(self):
        return f"[{self.get_kind_display()}] {self.title}"
