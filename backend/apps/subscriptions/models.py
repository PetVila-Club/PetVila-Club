from django.conf import settings
from django.db import models

from apps.catalog.models import SKU
from apps.core.models import TimeStampedModel
from apps.pets.models import Dog
from apps.plans.models import OfferVersion, Plan


class Subscription(TimeStampedModel):
    """ASS-01/PET-03: cada cão atendido tem o seu vínculo. Ração é uma recorrência independente (RAC-02)."""

    class Kind(models.TextChoices):
        KIT = "kit", "Kit PetVila"
        FOOD = "food", "Ração recorrente"

    class Status(models.TextChoices):
        PENDING = "pending", "Pendente (aguardando 1º pagamento)"
        ACTIVE = "active", "Ativa"
        PAST_DUE = "past_due", "Inadimplente"
        PAUSED = "paused", "Pausada"
        CANCELED = "canceled", "Cancelada"
        ENDED = "ended", "Encerrada"

    class BillingType(models.TextChoices):
        PIX = "PIX", "Pix"
        BOLETO = "BOLETO", "Boleto"
        CREDIT_CARD = "CREDIT_CARD", "Cartão de crédito"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="subscriptions", verbose_name="tutor")
    kind = models.CharField("tipo", max_length=10, choices=Kind.choices)
    status = models.CharField("situação", max_length=20, choices=Status.choices, default=Status.PENDING)
    dog = models.ForeignKey(Dog, null=True, blank=True, on_delete=models.PROTECT, related_name="subscriptions", verbose_name="cão")

    # Kit
    plan = models.ForeignKey(Plan, null=True, blank=True, on_delete=models.PROTECT, related_name="subscriptions", verbose_name="plano")
    offer = models.ForeignKey(OfferVersion, null=True, blank=True, on_delete=models.PROTECT, related_name="subscriptions",
                              verbose_name="oferta contratada")
    commitment_months = models.PositiveSmallIntegerField("ciclo de permanência (meses)", null=True, blank=True)

    # Ração
    sku = models.ForeignKey(SKU, null=True, blank=True, on_delete=models.PROTECT, related_name="food_subscriptions", verbose_name="SKU")
    quantity = models.PositiveSmallIntegerField("quantidade por entrega", default=1)
    frequency_days = models.PositiveSmallIntegerField("frequência (dias)", default=30)

    price_cents = models.PositiveIntegerField("valor por ciclo contratado (centavos)")
    shipping_cents = models.PositiveIntegerField("frete por ciclo (centavos)", default=0)
    currency = models.CharField(max_length=3, default="BRL")
    billing_type = models.CharField("meio de pagamento", max_length=20, choices=BillingType.choices)
    shipping_address = models.JSONField("endereço de entrega")
    started_at = models.DateTimeField("início", null=True, blank=True)
    next_billing_date = models.DateField("próxima cobrança", null=True, blank=True)
    cancel_requested_at = models.DateTimeField("cancelamento solicitado em", null=True, blank=True)
    cancel_effective_date = models.DateField("cancelamento efetivo em", null=True, blank=True)
    paused_at = models.DateTimeField(null=True, blank=True)

    accepted_terms = models.JSONField("aceite da oferta", default=dict)
    asaas_subscription_id = models.CharField("ID da assinatura no Asaas", max_length=40, unique=True, null=True, blank=True)
    checkout_key = models.CharField(max_length=120, null=True, blank=True)

    class Meta:
        verbose_name = "assinatura"
        verbose_name_plural = "assinaturas"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["user", "checkout_key", "dog", "kind"], name="subscription_checkout_idempotent"),
        ]

    def __str__(self):
        target = self.plan.name if self.plan else (self.sku.display_name if self.sku else "")
        who = f" · {self.dog.name}" if self.dog else ""
        return f"{self.number} {target}{who}"

    @property
    def number(self) -> str:
        return f"AS-{self.pk:06d}" if self.pk else "AS-novo"

    @property
    def total_per_cycle_cents(self) -> int:
        return self.price_cents + self.shipping_cents


class Cycle(TimeStampedModel):
    """Um ciclo por cobrança: vínculo único entre cobrança, kit e entrega (ASS-01)."""

    class Status(models.TextChoices):
        AWAITING_PAYMENT = "awaiting_payment", "Aguardando pagamento"
        PAYMENT_FAILED = "payment_failed", "Pagamento não confirmado"
        PAID = "paid", "Pago"
        CURATION = "curation", "Em curadoria"
        APPROVED = "approved", "Kit aprovado"
        RESERVED = "reserved", "Conteúdo fechado e reservado"
        PICKING = "picking", "Em separação"
        SHIPPED = "shipped", "Expedido"
        DELIVERED = "delivered", "Entregue"
        CANCELED = "canceled", "Cancelado"

    subscription = models.ForeignKey(Subscription, on_delete=models.PROTECT, related_name="cycles", verbose_name="assinatura")
    number = models.PositiveIntegerField("nº do ciclo")
    status = models.CharField("situação", max_length=20, choices=Status.choices, default=Status.AWAITING_PAYMENT)
    billing_date = models.DateField("data de cobrança", null=True, blank=True)
    cutoff_date = models.DateField("data de corte", null=True, blank=True)
    price_cents = models.PositiveIntegerField("valor do ciclo (centavos)")
    shipping_cents = models.PositiveIntegerField("frete (centavos)", default=0)
    offer_snapshot = models.JSONField("condição comercial aplicada", default=dict)
    external_payment_id = models.CharField("ID da cobrança no Asaas", max_length=40, unique=True, null=True, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "ciclo"
        verbose_name_plural = "ciclos"
        ordering = ["-created_at"]
        unique_together = [("subscription", "number")]

    def __str__(self):
        return f"{self.code} ({self.get_status_display()})"

    @property
    def code(self) -> str:
        return f"{self.subscription.number}-C{self.number:02d}"


class SubscriptionEvent(models.Model):
    subscription = models.ForeignKey(Subscription, on_delete=models.CASCADE, related_name="events")
    kind = models.CharField(max_length=60)
    detail = models.JSONField(default=dict, blank=True)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "histórico da assinatura"
        verbose_name_plural = "históricos de assinatura"

    def __str__(self):
        return f"{self.subscription.number} · {self.kind}"
