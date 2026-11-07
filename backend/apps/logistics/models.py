from django.conf import settings
from django.db import models

from apps.catalog.models import SKU
from apps.core.models import TimeStampedModel


class Shipment(TimeStampedModel):
    """Ordem de separação e expedição (LOG-01/02). Um kit por cão, um envio por pedido avulso."""

    class Kind(models.TextChoices):
        STORE = "store", "Pedido avulso"
        KIT = "kit", "Kit do ciclo"
        FOOD = "food", "Ração recorrente"
        RESEND = "resend", "Reenvio"

    class Status(models.TextChoices):
        PENDING = "pending", "Aguardando separação"
        PICKING = "picking", "Em separação"
        DIVERGENT = "divergent", "Conferência com divergência"
        CHECKED = "checked", "Conferido"
        SHIPPED = "shipped", "Expedido"
        DELIVERED = "delivered", "Entregue"
        EXCEPTION = "exception", "Ocorrência"
        CANCELED = "canceled", "Cancelado"

    kind = models.CharField("tipo", max_length=10, choices=Kind.choices)
    status = models.CharField("situação", max_length=20, choices=Status.choices, default=Status.PENDING)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="shipments")
    order = models.ForeignKey("orders.Order", null=True, blank=True, on_delete=models.PROTECT, related_name="shipments")
    cycle = models.ForeignKey("subscriptions.Cycle", null=True, blank=True, on_delete=models.PROTECT, related_name="shipments")
    resend_of = models.ForeignKey("self", null=True, blank=True, on_delete=models.PROTECT, related_name="resends",
                                  verbose_name="reenvio de")
    shipping_address = models.JSONField("endereço")
    carrier = models.CharField("transportador", max_length=80, blank=True)
    service = models.CharField("serviço", max_length=80, blank=True)
    tracking_code = models.CharField("rastreio", max_length=80, blank=True)
    tracking_url = models.URLField("link de rastreio", blank=True)
    label_registered_at = models.DateTimeField("etiqueta registrada em", null=True, blank=True)
    divergences = models.JSONField("divergências da conferência", default=list, blank=True)
    checked_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+",
                                   verbose_name="conferido por")
    shipped_at = models.DateTimeField("expedido em", null=True, blank=True)
    delivered_at = models.DateTimeField("entregue em", null=True, blank=True)
    delivery_source = models.CharField("entrega informada por", max_length=20, blank=True)

    class Meta:
        verbose_name = "expedição"
        verbose_name_plural = "expedições"
        ordering = ["status", "created_at"]
        constraints = [
            models.UniqueConstraint(fields=["order"], condition=models.Q(resend_of__isnull=True, order__isnull=False),
                                    name="one_primary_shipment_per_order"),
            models.UniqueConstraint(fields=["cycle"], condition=models.Q(resend_of__isnull=True, cycle__isnull=False),
                                    name="one_primary_shipment_per_cycle"),
        ]

    def __str__(self):
        return f"{self.number} · {self.get_status_display()}"

    @property
    def number(self) -> str:
        return f"EX-{self.pk:06d}" if self.pk else "EX-novo"


class ShipmentLine(models.Model):
    shipment = models.ForeignKey(Shipment, on_delete=models.CASCADE, related_name="lines")
    sku = models.ForeignKey(SKU, on_delete=models.PROTECT)
    sku_code = models.CharField(max_length=40)
    product_name = models.CharField(max_length=200)
    quantity = models.PositiveIntegerField("quantidade")
    dog = models.ForeignKey("pets.Dog", null=True, blank=True, on_delete=models.PROTECT, related_name="+", verbose_name="cão destino")
    kit_line = models.ForeignKey("curation.KitLine", null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    order_line = models.ForeignKey("orders.OrderLine", null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    reserve_key = models.CharField(max_length=160)
    lot = models.ForeignKey("inventory.Lot", null=True, blank=True, on_delete=models.PROTECT, related_name="+")

    class Meta:
        verbose_name = "item da expedição"
        verbose_name_plural = "itens da expedição"

    def __str__(self):
        return f"{self.quantity} × {self.sku_code}" + (f" → {self.dog.name}" if self.dog_id else "")


class Incident(TimeStampedModel):
    """LOG-03: atraso, extravio, avaria, entrega parcial, devolução e reenvio."""

    class Kind(models.TextChoices):
        DELAY = "delay", "Atraso"
        LOST = "lost", "Extravio"
        DAMAGED = "damaged", "Avaria"
        PARTIAL = "partial", "Entrega parcial"
        RETURN = "return", "Devolução"
        COMPLAINT = "complaint", "Reclamação do tutor"

    class Source(models.TextChoices):
        CARRIER = "carrier", "Transportador"
        TUTOR = "tutor", "Tutor"
        OPERATION = "operation", "Operação"

    class Status(models.TextChoices):
        OPEN = "open", "Aberta"
        RESOLVED = "resolved", "Resolvida"

    shipment = models.ForeignKey(Shipment, on_delete=models.PROTECT, related_name="incidents")
    kind = models.CharField("tipo", max_length=20, choices=Kind.choices)
    source = models.CharField("origem", max_length=20, choices=Source.choices)
    status = models.CharField("situação", max_length=20, choices=Status.choices, default=Status.OPEN)
    description = models.TextField("descrição")
    resolution = models.TextField("solução", blank=True)
    resend = models.ForeignKey(Shipment, null=True, blank=True, on_delete=models.PROTECT, related_name="+", verbose_name="reenvio gerado")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")

    class Meta:
        verbose_name = "ocorrência de entrega"
        verbose_name_plural = "ocorrências de entrega"
        ordering = ["status", "-created_at"]

    def __str__(self):
        return f"{self.get_kind_display()} · {self.shipment.number}"
