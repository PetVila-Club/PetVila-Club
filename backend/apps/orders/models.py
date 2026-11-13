from django.conf import settings
from django.db import models

from apps.catalog.models import SKU
from apps.core.models import TimeStampedModel


class ShippingZone(TimeStampedModel):
    """CHK-02: atendimento por faixa de CEP. CEP fora de faixa ativa bloqueia a compra."""

    name = models.CharField("nome", max_length=80)
    cep_start = models.CharField("CEP inicial", max_length=8)
    cep_end = models.CharField("CEP final", max_length=8)
    price_cents = models.PositiveIntegerField("frete (centavos)")
    eta_days = models.PositiveSmallIntegerField("prazo (dias úteis)")
    free_above_cents = models.PositiveIntegerField("frete grátis acima de (centavos)", null=True, blank=True)
    is_active = models.BooleanField("ativa", default=True)

    class Meta:
        verbose_name = "região de entrega"
        verbose_name_plural = "regiões de entrega"
        ordering = ["cep_start"]

    def __str__(self):
        return f"{self.name} ({self.cep_start}–{self.cep_end})"

    @classmethod
    def for_cep(cls, cep: str) -> "ShippingZone | None":
        digits = "".join(ch for ch in cep if ch.isdigit())
        if len(digits) != 8:
            return None
        return cls.objects.filter(is_active=True, cep_start__lte=digits, cep_end__gte=digits).order_by("price_cents").first()


class Order(TimeStampedModel):
    """Pedido avulso da loja. Assinaturas geram ciclos próprios; os fluxos não se misturam no MVP."""

    class Status(models.TextChoices):
        PENDING_PAYMENT = "pending_payment", "Aguardando pagamento"
        PAID = "paid", "Pago"
        FULFILLING = "fulfilling", "Em separação"
        SHIPPED = "shipped", "Expedido"
        DELIVERED = "delivered", "Entregue"
        CANCELED = "canceled", "Cancelado"
        REFUNDED = "refunded", "Estornado"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="orders", verbose_name="cliente")
    status = models.CharField("situação", max_length=20, choices=Status.choices, default=Status.PENDING_PAYMENT)
    subtotal_cents = models.PositiveIntegerField("subtotal (centavos)")
    discount_cents = models.PositiveIntegerField("descontos (centavos)", default=0)
    shipping_cents = models.PositiveIntegerField("frete (centavos)", default=0)
    total_cents = models.PositiveIntegerField("total (centavos)")
    currency = models.CharField(max_length=3, default="BRL")
    member_pricing = models.BooleanField("preço de assinante aplicado", default=False)
    shipping_address = models.JSONField("endereço de entrega")
    shipping_zone = models.CharField("região", max_length=80, blank=True)
    eta_days = models.PositiveSmallIntegerField("prazo (dias úteis)", null=True, blank=True)
    billing_type = models.CharField("meio de pagamento", max_length=20)
    accepted_terms = models.JSONField("aceite", default=dict)
    idempotency_key = models.CharField(max_length=120)
    paid_at = models.DateTimeField(null=True, blank=True)
    canceled_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField("expira em (sem pagamento)", null=True, blank=True)

    class Meta:
        verbose_name = "pedido avulso"
        verbose_name_plural = "pedidos avulsos"
        ordering = ["-created_at"]
        constraints = [models.UniqueConstraint(fields=["user", "idempotency_key"], name="order_idempotency_per_user")]

    def __str__(self):
        return f"{self.number} ({self.get_status_display()})"

    @property
    def number(self) -> str:
        return f"PV-{self.pk:06d}" if self.pk else "PV-novo"


class OrderLine(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="lines")
    sku = models.ForeignKey(SKU, on_delete=models.PROTECT, related_name="order_lines")
    sku_code = models.CharField(max_length=40)
    product_name = models.CharField(max_length=160)
    variant_name = models.CharField(max_length=80, blank=True)
    quantity = models.PositiveIntegerField()
    list_price_cents = models.PositiveIntegerField("preço de tabela (centavos)")
    unit_price_cents = models.PositiveIntegerField("preço cobrado (centavos)")
    unit_cost_cents = models.PositiveIntegerField("custo no fechamento (centavos)", default=0)

    class Meta:
        verbose_name = "linha do pedido"
        verbose_name_plural = "linhas do pedido"

    def __str__(self):
        return f"{self.quantity} × {self.sku_code}"

    @property
    def total_cents(self) -> int:
        return self.unit_price_cents * self.quantity

    @property
    def reserve_key(self) -> str:
        return f"order:{self.order_id}:line:{self.pk}:reserve"
