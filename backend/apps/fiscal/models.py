from django.conf import settings
from django.db import models

from apps.core.models import TimeStampedModel


class FiscalDocument(TimeStampedModel):
    """
    FIS-01/02. Enquanto não houver emissor homologado, o procedimento é assistido:
    o financeiro emite no sistema fiscal e registra aqui número, chave e situação.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Pendente de emissão"
        AUTHORIZED = "authorized", "Autorizado"
        REJECTED = "rejected", "Rejeitado"
        CANCELED = "canceled", "Cancelado"
        NOT_REQUIRED = "not_required", "Não aplicável (decisão fiscal registrada)"

    class Procedure(models.TextChoices):
        ASSISTED = "assisted", "Procedimento assistido"
        PROVIDER = "provider", "Emissor integrado"

    shipment = models.ForeignKey("logistics.Shipment", on_delete=models.PROTECT, related_name="fiscal_documents")
    status = models.CharField("situação", max_length=20, choices=Status.choices, default=Status.PENDING)
    procedure = models.CharField("procedimento", max_length=20, choices=Procedure.choices, default=Procedure.ASSISTED)
    document_type = models.CharField("documento", max_length=20, default="NF-e")
    number = models.CharField("número", max_length=20, blank=True)
    series = models.CharField("série", max_length=5, blank=True)
    access_key = models.CharField("chave de acesso", max_length=60, blank=True)
    file_url = models.URLField("arquivo (PDF/XML)", blank=True)
    amount_cents = models.PositiveIntegerField("valor (centavos)", default=0)
    rejection_reason = models.TextField("motivo da rejeição", blank=True)
    decision_note = models.TextField("registro da decisão fiscal", blank=True)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")

    class Meta:
        verbose_name = "documento fiscal"
        verbose_name_plural = "documentos fiscais"
        ordering = ["status", "-created_at"]

    def __str__(self):
        return f"{self.document_type} {self.number or '(sem número)'} · {self.get_status_display()}"
