from django.conf import settings
from django.db import models

from apps.core.models import TimeStampedModel


class Ticket(TimeStampedModel):
    """VIL-03 / PRV-02: toda solicitação gera protocolo e estado rastreável."""

    class Kind(models.TextChoices):
        EXCHANGE = "exchange", "Troca"
        CANCELLATION = "cancellation", "Cancelamento"
        PRIVACY_ACCESS = "privacy_access", "LGPD · acesso aos dados"
        PRIVACY_CORRECTION = "privacy_correction", "LGPD · correção"
        PRIVACY_DELETION = "privacy_deletion", "LGPD · exclusão"
        PAYMENT = "payment", "Pagamento"
        DELIVERY = "delivery", "Entrega"
        FEEDBACK = "feedback", "Feedback de produto"
        OTHER = "other", "Outro assunto"

    class Status(models.TextChoices):
        RECEIVED = "received", "Recebida"
        IN_PROGRESS = "in_progress", "Em andamento"
        WAITING_CUSTOMER = "waiting_customer", "Aguardando você"
        RESOLVED = "resolved", "Concluída"
        CLOSED = "closed", "Encerrada"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="tickets")
    kind = models.CharField("assunto", max_length=30, choices=Kind.choices)
    status = models.CharField("situação", max_length=20, choices=Status.choices, default=Status.RECEIVED)
    subject = models.CharField("título", max_length=160)
    description = models.TextField("descrição")
    reference = models.CharField("pedido/assinatura relacionada", max_length=40, blank=True)
    due_at = models.DateTimeField("prazo de retorno", null=True, blank=True)
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+",
                                    verbose_name="responsável")
    resolution = models.TextField("resposta final", blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "solicitação"
        verbose_name_plural = "solicitações (atendimento)"
        ordering = ["status", "-created_at"]

    def __str__(self):
        return f"{self.protocol} · {self.subject}"

    @property
    def protocol(self) -> str:
        return f"PV{self.created_at:%Y}-{self.pk:06d}" if self.pk and self.created_at else "PV-novo"


class TicketMessage(models.Model):
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name="messages")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    body = models.TextField("mensagem")
    internal = models.BooleanField("nota interna (não visível ao tutor)", default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        verbose_name = "mensagem"
        verbose_name_plural = "mensagens"

    def __str__(self):
        return f"{self.ticket.protocol} · {self.author}"
