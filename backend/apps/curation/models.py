from django.conf import settings
from django.db import models

from apps.catalog.models import SKU, Category
from apps.core.models import TimeStampedModel
from apps.pets.models import Dog, DogProfileVersion
from apps.plans.models import CompositionVersion, KitModel
from apps.subscriptions.models import Cycle


class CycleKit(TimeStampedModel):
    """
    Kit de um cão em um ciclo (KIT-04). Ao fechar, guarda cópia imutável de plano,
    composição, modelo, perfil, SKUs, quantidades e valores.
    """

    class Status(models.TextChoices):
        SUGGESTED = "suggested", "Sugestão pronta"
        NEEDS_REVIEW = "needs_review", "Exige revisão"
        APPROVED = "approved", "Aprovado pela curadoria"
        REJECTED = "rejected", "Rejeitado"
        CLOSED = "closed", "Fechado e reservado"

    cycle = models.OneToOneField(Cycle, on_delete=models.PROTECT, related_name="kit", verbose_name="ciclo")
    dog = models.ForeignKey(Dog, on_delete=models.PROTECT, related_name="kits", verbose_name="cão")
    status = models.CharField("situação", max_length=20, choices=Status.choices, default=Status.SUGGESTED)
    group_key = models.CharField("grupo sugerido", max_length=160, blank=True, db_index=True)
    profile_version = models.ForeignKey(DogProfileVersion, on_delete=models.PROTECT, related_name="+", verbose_name="versão do perfil")
    composition = models.ForeignKey(CompositionVersion, on_delete=models.PROTECT, related_name="+", verbose_name="composição")
    kit_model = models.ForeignKey(KitModel, null=True, blank=True, on_delete=models.PROTECT, related_name="+", verbose_name="modelo")
    engine_version = models.CharField("versão das regras", max_length=20)
    trace = models.JSONField("rastro da sugestão", default=dict, blank=True)
    review_reasons = models.JSONField("motivos de revisão", default=list, blank=True)
    snapshot = models.JSONField("cópia imutável no fechamento", default=dict, blank=True)
    decision_note = models.TextField("justificativa da curadoria", blank=True)
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+",
                                    verbose_name="aprovado por")
    approved_at = models.DateTimeField("aprovado em", null=True, blank=True)
    closed_at = models.DateTimeField("fechado em", null=True, blank=True)

    class Meta:
        verbose_name = "kit do ciclo"
        verbose_name_plural = "curadoria · kits dos ciclos"
        ordering = ["status", "-created_at"]

    def __str__(self):
        return f"Kit {self.cycle.code} · {self.dog.name}"

    @property
    def active_lines(self):
        return self.lines.filter(status=KitLine.Status.ACTIVE)


class KitLine(models.Model):
    """Linha do kit. Substituição nunca apaga: a linha antiga fica registrada como substituída."""

    class Status(models.TextChoices):
        ACTIVE = "active", "Vigente"
        SUBSTITUTED = "substituted", "Substituída"
        REMOVED = "removed", "Removida"

    kit = models.ForeignKey(CycleKit, on_delete=models.CASCADE, related_name="lines")
    category = models.ForeignKey(Category, on_delete=models.PROTECT, verbose_name="categoria")
    sku = models.ForeignKey(SKU, on_delete=models.PROTECT, verbose_name="SKU")
    quantity = models.PositiveSmallIntegerField("quantidade")
    unit_cost_cents = models.PositiveIntegerField("custo no fechamento (centavos)", default=0)
    status = models.CharField("situação", max_length=20, choices=Status.choices, default=Status.ACTIVE)
    replaces = models.ForeignKey("self", null=True, blank=True, on_delete=models.PROTECT, related_name="replaced_by",
                                 verbose_name="substitui")
    justification = models.TextField("justificativa", blank=True)
    decided_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+",
                                   verbose_name="decidido por")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "linha do kit"
        verbose_name_plural = "linhas do kit"
        ordering = ["category__sort", "id"]

    def __str__(self):
        return f"{self.quantity} × {self.sku.code} ({self.get_status_display()})"

    @property
    def reserve_key(self) -> str:
        return f"kitline:{self.pk}:reserve"
