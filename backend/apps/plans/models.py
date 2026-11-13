from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone

from apps.catalog.models import SKU, Category
from apps.core.models import TimeStampedModel


class Plan(TimeStampedModel):
    code = models.SlugField("código", unique=True)
    name = models.CharField("nome", max_length=80)
    tagline = models.CharField("frase", max_length=160, blank=True)
    description = models.TextField("descrição", blank=True)
    base_item_count = models.PositiveSmallIntegerField(
        "total de itens prometido", help_text="Base pública (7 no Essential, 10 no Care). Mudar exige nova versão de oferta."
    )
    highlight = models.BooleanField("destaque", default=False)
    extras = models.JSONField("destaques extras (ex.: Originals)", default=list, blank=True)
    is_active = models.BooleanField("ativo", default=True)
    sort = models.PositiveSmallIntegerField("ordem", default=0)

    class Meta:
        verbose_name = "plano"
        verbose_name_plural = "planos"
        ordering = ["sort"]

    def __str__(self):
        return self.name

    def current_offer(self, at=None) -> "OfferVersion | None":
        at = at or timezone.now()
        return (
            self.offers.filter(status=OfferVersion.Status.PUBLISHED, valid_from__lte=at)
            .filter(Q(valid_until__isnull=True) | Q(valid_until__gt=at))
            .order_by("-valid_from", "-version")
            .first()
        )

    def current_composition(self, at=None) -> "CompositionVersion | None":
        at = at or timezone.now()
        return (
            self.compositions.filter(status=CompositionVersion.Status.PUBLISHED, valid_from__lte=at)
            .order_by("-valid_from", "-version")
            .first()
        )


class OfferVersion(TimeStampedModel):
    """COM-01/02: condição comercial versionada, separada do custo."""

    class Status(models.TextChoices):
        DRAFT = "draft", "Rascunho"
        APPROVED = "approved", "Aprovada"
        PUBLISHED = "published", "Publicada"
        ARCHIVED = "archived", "Arquivada"

    plan = models.ForeignKey(Plan, on_delete=models.PROTECT, related_name="offers", verbose_name="plano")
    version = models.PositiveIntegerField("versão")
    status = models.CharField("situação", max_length=20, choices=Status.choices, default=Status.DRAFT)
    price_cents = models.PositiveIntegerField("preço mensal (centavos)", null=True, blank=True,
                                              help_text="Vazio = preço pendente. Não pode ser publicada sem preço aprovado.")
    currency = models.CharField(max_length=3, default="BRL")
    billing_cycle = models.CharField("periodicidade da cobrança", max_length=20, default="MONTHLY", editable=False)
    commitment_options = models.JSONField("ciclos de permanência (meses)", default=list, blank=True)
    shipping_cents = models.PositiveIntegerField("frete por entrega (centavos)", default=0)
    benefits = models.TextField("benefícios aprovados", blank=True)
    terms = models.TextField("condições de contratação", blank=True)
    internal_notes = models.TextField("observações internas (não publicadas)", blank=True)
    valid_from = models.DateTimeField("vigência a partir de", null=True, blank=True)
    valid_until = models.DateTimeField("vigência até", null=True, blank=True)
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+",
                                    verbose_name="aprovada por")
    approved_at = models.DateTimeField("aprovada em", null=True, blank=True)
    approval_note = models.TextField("registro da aprovação", blank=True)
    published_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+",
                                     verbose_name="publicada por")
    published_at = models.DateTimeField("publicada em", null=True, blank=True)

    class Meta:
        verbose_name = "oferta (versão comercial)"
        verbose_name_plural = "ofertas (versões comerciais)"
        unique_together = [("plan", "version")]
        ordering = ["plan", "-version"]

    def __str__(self):
        return f"{self.plan.name} · oferta v{self.version} ({self.get_status_display()})"

    def snapshot(self) -> dict:
        return {
            "offer_id": self.pk,
            "plan": self.plan.code,
            "version": self.version,
            "price_cents": self.price_cents,
            "currency": self.currency,
            "billing_cycle": self.billing_cycle,
            "shipping_cents": self.shipping_cents,
            "commitment_options": self.commitment_options,
            "benefits": self.benefits,
            "terms": self.terms,
        }


class CompositionVersion(TimeStampedModel):
    """KIT-01/03: composição editável por plano, com ciclo de vida e vigência."""

    class Status(models.TextChoices):
        DRAFT = "draft", "Rascunho"
        IN_REVIEW = "in_review", "Em revisão"
        APPROVED = "approved", "Aprovada"
        PUBLISHED = "published", "Publicada"
        ARCHIVED = "archived", "Arquivada"

    plan = models.ForeignKey(Plan, on_delete=models.PROTECT, related_name="compositions", verbose_name="plano")
    version = models.PositiveIntegerField("versão")
    status = models.CharField("situação", max_length=20, choices=Status.choices, default=Status.DRAFT)
    notes = models.TextField("notas da versão", blank=True)
    valid_from = models.DateTimeField("vigência a partir de", null=True, blank=True)
    total_change_confirmed = models.BooleanField(
        "confirmo mudança do total prometido", default=False,
        help_text="Obrigatório quando a soma difere do total do plano; exige também revisão da oferta.",
    )
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+",
                                    verbose_name="aprovada por")
    approved_at = models.DateTimeField(null=True, blank=True)
    published_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+",
                                     verbose_name="publicada por")
    published_at = models.DateTimeField(null=True, blank=True)
    previous = models.ForeignKey("self", null=True, blank=True, on_delete=models.PROTECT, related_name="+",
                                 verbose_name="versão anterior")

    class Meta:
        verbose_name = "composição do plano"
        verbose_name_plural = "composições dos planos"
        unique_together = [("plan", "version")]
        ordering = ["plan", "-version"]

    def __str__(self):
        return f"{self.plan.name} · composição v{self.version} ({self.get_status_display()})"

    @property
    def total_items(self) -> int:
        return sum(line.quantity for line in self.lines.all() if line.counts_toward_total)

    def snapshot(self) -> dict:
        return {
            "composition_id": self.pk,
            "plan": self.plan.code,
            "version": self.version,
            "lines": [
                {"category": line.category.slug, "category_name": line.category.name, "quantity": line.quantity}
                for line in self.lines.select_related("category").order_by("category__sort")
            ],
            "total_items": self.total_items,
        }


class CompositionLine(models.Model):
    composition = models.ForeignKey(CompositionVersion, on_delete=models.CASCADE, related_name="lines")
    category = models.ForeignKey(Category, on_delete=models.PROTECT, limit_choices_to={"is_kit_category": True},
                                 verbose_name="categoria")
    quantity = models.IntegerField("quantidade (unidades comerciais)")
    counts_toward_total = models.BooleanField("conta no total", default=True)

    class Meta:
        verbose_name = "linha da composição"
        verbose_name_plural = "linhas da composição"
        # Uma categoria só pode aparecer uma vez: evita item contado duas vezes.
        unique_together = [("composition", "category")]

    def __str__(self):
        return f"{self.quantity} × {self.category.name}"


class KitModel(TimeStampedModel):
    """KIT-02: alternativas de seleção dentro de um plano (não são novos planos)."""

    class Status(models.TextChoices):
        ACTIVE = "active", "Ativo"
        ARCHIVED = "archived", "Arquivado"

    plan = models.ForeignKey(Plan, on_delete=models.PROTECT, related_name="kit_models", verbose_name="plano")
    name = models.CharField("nome", max_length=80)
    description = models.TextField("descrição", blank=True)
    status = models.CharField("situação", max_length=20, choices=Status.choices, default=Status.ACTIVE)
    skus = models.ManyToManyField(SKU, blank=True, related_name="kit_models", verbose_name="SKUs elegíveis",
                                  help_text="Vazio = todos os SKUs ativos das categorias da composição.")

    class Meta:
        verbose_name = "modelo de kit"
        verbose_name_plural = "modelos de kit"
        ordering = ["plan", "name"]

    def __str__(self):
        return f"{self.plan.name} · {self.name}"

    def clean(self):
        from django.core.exceptions import ValidationError

        from apps.core.exceptions import DomainError

        from .services import check_kit_model_limit

        if self.status == self.Status.ACTIVE and self.plan_id:
            was_active = self.pk and KitModel.objects.filter(pk=self.pk, status=self.Status.ACTIVE).exists()
            if not was_active:
                try:
                    check_kit_model_limit(self.plan, exclude_pk=self.pk)
                except DomainError as exc:
                    raise ValidationError(exc.message) from exc
