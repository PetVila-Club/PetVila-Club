import hmac
import json
import logging
import uuid

from django.conf import settings
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import api_view, authentication_classes, permission_classes, throttle_classes
from rest_framework.response import Response

from .models import Payment
from .serializers import PaymentSerializer
from .services import process_event

logger = logging.getLogger(__name__)


@api_view(["POST"])
@authentication_classes([])
@permission_classes([permissions.AllowAny])
@throttle_classes([])
def asaas_webhook(request):
    """PAG-02: autenticidade pelo token configurado no Asaas (header asaas-access-token)."""
    expected = settings.ASAAS_WEBHOOK_TOKEN
    received = request.headers.get("asaas-access-token", "")
    if not expected or not hmac.compare_digest(expected.encode(), received.encode()):
        logger.warning("Webhook Asaas rejeitado: token inválido")
        return Response({"detail": "unauthorized"}, status=status.HTTP_401_UNAUTHORIZED)
    payload = request.data if isinstance(request.data, dict) else json.loads(request.body or b"{}")
    result = process_event(payload)
    # Sempre 200 para eventos autênticos: falhas ficam registradas e são reprocessadas pelo painel,
    # sem travar a fila de webhooks do provedor.
    return Response({"received": True, "result": result})


@api_view(["POST"])
def simulate_payment(request):
    """Somente com o provedor simulado: dispara o mesmo fluxo de webhook para testar localmente."""
    if not settings.PAYMENTS_FAKE_MODE:
        return Response({"detail": "Indisponível com o provedor real."}, status=status.HTTP_404_NOT_FOUND)
    payment = Payment.objects.filter(external_id=request.data.get("external_id"), user=request.user).first()
    if payment is None:
        return Response({"detail": "Cobrança não encontrada."}, status=status.HTTP_404_NOT_FOUND)
    outcome = request.data.get("outcome", "paid")
    event, new_status = {
        "paid": ("PAYMENT_CONFIRMED", "CONFIRMED"),
        "received": ("PAYMENT_RECEIVED", "RECEIVED"),
        "overdue": ("PAYMENT_OVERDUE", "OVERDUE"),
        "deleted": ("PAYMENT_DELETED", payment.status),
    }.get(outcome, ("PAYMENT_CONFIRMED", "CONFIRMED"))
    payload = {
        "id": f"evt_sim_{uuid.uuid4().hex[:12]}",
        "event": event,
        "payment": {
            "id": payment.external_id,
            "subscription": payment.external_subscription_id or None,
            "status": new_status,
            "value": payment.value_cents / 100,
            "billingType": payment.billing_type,
            "dueDate": payment.due_date.isoformat() if payment.due_date else None,
        },
    }
    result = process_event(payload)
    payment.refresh_from_db()
    return Response({"result": result, "payment": PaymentSerializer(payment).data})


class MyPaymentViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = PaymentSerializer

    def get_queryset(self):
        return Payment.objects.filter(user=self.request.user).select_related("order", "cycle__subscription", "subscription")
