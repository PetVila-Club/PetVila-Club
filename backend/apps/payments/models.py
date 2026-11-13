from django.conf import settings
from django.db import models

from apps.core.models import TimeStampedModel

# Ordem lógica dos estados do Asaas. Evento atrasado com estado "anterior" não regride o pagamento (PAG-02).
STATUS_RANK = {
    "PENDING": 10,
    "AWAITING_RISK_ANALYSIS": 15,
    "OVERDUE": 20,
    "CONFIRMED": 40,
    "RECEIVED": 50,
    "RECEIVED_IN_CASH": 50,
    "DUNNING_REQUESTED": 55,
    "DUNNING_RECEIVED": 60,
    "AWAITING_CHARGEBACK_REVERSAL": 70,
    "CHARGEBACK_REQUESTED": 75,
    "CHARGEBACK_DISPUTE": 76,
    "REFUND_REQUESTED": 78,
    "REFUND_IN_PROGRESS": 79,
    "REFUNDED": 90,
    "DELETED": 95,
}
PAID_STATUSES = {"CONFIRMED", "RECEIVED", "RECEIVED_IN_CASH", "DUNNING_RECEIVED"}


class Payment(TimeStampedModel):
    class Purpose(models.TextChoices):
        ORDER = "order", "Pedido avulso"
        SUBSCRIPTION = "subscription", "Ciclo de assinatura"

    provider = models.CharField(max_length=20, default="asaas")
    purpose = models.CharField("finalidade", max_length=20, choices=Purpose.choices)
    external_id = models.CharField("ID no Asaas", max_length=40, unique=True)
    external_subscription_id = models.CharField("ID da assinatura no Asaas", max_length=40, blank=True, db_index=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="payments")
    order = models.ForeignKey("orders.Order", null=True, blank=True, on_delete=models.PROTECT, related_name="payments")
    subscription = models.ForeignKey("subscriptions.Subscription", null=True, blank=True, on_delete=models.PROTECT,
                                     related_name="payments")
    cycle = models.ForeignKey("subscriptions.Cycle", null=True, blank=True, on_delete=models.PROTECT, related_name="payments")
    billing_type = models.CharField("meio", max_length=20)
    status = models.CharField("situação no provedor", max_length=40, default="PENDING")
    value_cents = models.PositiveIntegerField("valor (centavos)")
    net_value_cents = models.PositiveIntegerField("valor líquido (centavos)", null=True, blank=True)
    refunded_cents = models.PositiveIntegerField("estornado (centavos)", default=0)
    due_date = models.DateField("vencimento", null=True, blank=True)
    invoice_url = models.URLField("fatura", max_length=500, blank=True)
    bank_slip_url = models.URLField("boleto", max_length=500, blank=True)
    pix_payload = models.TextField("Pix copia e cola", blank=True)
    pix_qr_image = models.TextField("QR Code Pix (base64)", blank=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    last_event_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "cobrança"
        verbose_name_plural = "cobranças"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.external_id} · {self.status}"

    @property
    def is_paid(self) -> bool:
        return self.status in PAID_STATUSES

    @property
    def status_label(self) -> str:
        return {
            "PENDING": "Aguardando pagamento",
            "OVERDUE": "Vencida",
            "CONFIRMED": "Pagamento confirmado",
            "RECEIVED": "Pagamento recebido",
            "RECEIVED_IN_CASH": "Pagamento recebido",
            "REFUNDED": "Estornada",
            "REFUND_REQUESTED": "Estorno solicitado",
            "REFUND_IN_PROGRESS": "Estorno em andamento",
            "DELETED": "Cancelada",
            "CHARGEBACK_REQUESTED": "Contestação aberta",
            "CHARGEBACK_DISPUTE": "Contestação em disputa",
            "AWAITING_RISK_ANALYSIS": "Em análise",
        }.get(self.status, self.status)


class PaymentEvent(models.Model):
    """Registro bruto de cada webhook recebido. O ID do evento garante processamento único."""

    external_event_id = models.CharField("ID do evento", max_length=80, unique=True)
    event_type = models.CharField("evento", max_length=60)
    payment_external_id = models.CharField(max_length=40, blank=True, db_index=True)
    payload = models.JSONField()
    received_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    result = models.CharField(max_length=200, blank=True)
    error = models.TextField(blank=True)

    class Meta:
        verbose_name = "evento do provedor"
        verbose_name_plural = "eventos do provedor"
        ordering = ["-received_at"]

    def __str__(self):
        return f"{self.event_type} · {self.payment_external_id}"


class Refund(TimeStampedModel):
    class Status(models.TextChoices):
        REQUESTED = "requested", "Solicitado"
        DONE = "done", "Executado"
        FAILED = "failed", "Falhou"

    payment = models.ForeignKey(Payment, on_delete=models.PROTECT, related_name="refunds")
    value_cents = models.PositiveIntegerField("valor (centavos)")
    reason = models.TextField("motivo")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.REQUESTED)
    idempotency_key = models.CharField(max_length=120, unique=True)
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    error = models.TextField(blank=True)

    class Meta:
        verbose_name = "estorno"
        verbose_name_plural = "estornos"

    def __str__(self):
        return f"Estorno {self.value_cents / 100:.2f} · {self.payment.external_id}"
