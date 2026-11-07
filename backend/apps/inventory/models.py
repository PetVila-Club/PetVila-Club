from django.conf import settings
from django.db import models

from apps.catalog.models import SKU


class StockLevel(models.Model):
    """EST-01: saldo físico, reservado, avariado, em trânsito e em quarentena por SKU."""

    sku = models.OneToOneField(SKU, on_delete=models.PROTECT, related_name="stock")
    physical = models.IntegerField("físico (apto)", default=0)
    reserved = models.IntegerField("reservado", default=0)
    damaged = models.IntegerField("avariado", default=0)
    in_transit = models.IntegerField("em trânsito (compras)", default=0)
    quarantine = models.IntegerField("em inspeção (devoluções)", default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "saldo de estoque"
        verbose_name_plural = "saldos de estoque"
        constraints = [
            models.CheckConstraint(condition=models.Q(physical__gte=0), name="stock_physical_gte_0"),
            models.CheckConstraint(condition=models.Q(reserved__gte=0), name="stock_reserved_gte_0"),
            models.CheckConstraint(condition=models.Q(reserved__lte=models.F("physical")), name="stock_reserved_lte_physical"),
        ]

    def __str__(self):
        return f"{self.sku.code}: {self.available} disponíveis"

    @property
    def available(self) -> int:
        return self.physical - self.reserved


class Lot(models.Model):
    """EST-02: lote, validade e conservação."""

    sku = models.ForeignKey(SKU, on_delete=models.PROTECT, related_name="lots")
    code = models.CharField("lote", max_length=60)
    expires_on = models.DateField("validade", null=True, blank=True)
    received_on = models.DateField("recebido em")
    quantity_received = models.PositiveIntegerField("quantidade recebida")
    quantity_remaining = models.PositiveIntegerField("saldo do lote")
    storage_conditions = models.CharField("armazenamento", max_length=200, blank=True)
    is_blocked = models.BooleanField("bloqueado (qualidade)", default=False)

    class Meta:
        verbose_name = "lote"
        verbose_name_plural = "lotes"
        ordering = ["sku", "expires_on"]
        unique_together = [("sku", "code")]

    def __str__(self):
        return f"{self.sku.code} · lote {self.code}" + (f" · val. {self.expires_on:%d/%m/%Y}" if self.expires_on else "")


class StockMovement(models.Model):
    class Kind(models.TextChoices):
        ENTRY = "entry", "Entrada"
        RESERVE = "reserve", "Reserva"
        RELEASE = "release", "Liberação de reserva"
        SHIP = "ship", "Baixa por expedição"
        ADJUST = "adjust", "Ajuste"
        DAMAGE = "damage", "Avaria"
        RETURN_QUARANTINE = "return_quarantine", "Devolução para inspeção"
        RETURN_APPROVED = "return_approved", "Devolução aprovada (volta a vendável)"
        RETURN_REJECTED = "return_rejected", "Devolução reprovada (descarte)"

    sku = models.ForeignKey(SKU, on_delete=models.PROTECT, related_name="movements")
    kind = models.CharField("tipo", max_length=30, choices=Kind.choices)
    quantity = models.IntegerField("quantidade")
    lot = models.ForeignKey(Lot, null=True, blank=True, on_delete=models.PROTECT)
    reason = models.CharField("motivo", max_length=255, blank=True)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    reference_type = models.CharField(max_length=60, blank=True)
    reference_id = models.CharField(max_length=64, blank=True)
    idempotency_key = models.CharField(max_length=160, unique=True, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "movimentação de estoque"
        verbose_name_plural = "movimentações de estoque"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.get_kind_display()} {self.quantity} × {self.sku.code}"
