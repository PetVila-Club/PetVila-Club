"""
Pagamentos (PAG-01/02/03).

- Webhooks são deduplicados pelo ID do evento e o estado nunca regride (evento atrasado é registrado e ignorado).
- A liberação (pedido pago, ciclo pago) acontece uma única vez, protegida por SELECT FOR UPDATE.
- Estornos são idempotentes e limitados ao valor efetivamente capturado.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.core.exceptions import DomainError
from apps.core.models import OperationalAlert
from apps.core.services import Roles, audit, get_setting, has_role, raise_alert, require_role

from .asaas import AsaasError, get_client, value_to_cents
from .models import PAID_STATUSES, STATUS_RANK, Payment, PaymentEvent, Refund

logger = logging.getLogger(__name__)


def ensure_customer(user) -> str:
    if user.asaas_customer_id:
        return user.asaas_customer_id
    if not user.cpf:
        raise DomainError("Informe seu CPF em Minha Vila > Meus dados para concluir o pagamento.", code="cpf_required")
    try:
        data = get_client().create_customer(name=user.full_name, cpf_cnpj=user.cpf, email=user.email,
                                            phone=user.phone, external_reference=f"user:{user.pk}")
    except AsaasError as exc:
        raise DomainError(f"Não foi possível registrar o cliente no provedor de pagamento: {exc}", code="provider_error",
                          status_code=502) from exc
    user.asaas_customer_id = data["id"]
    user.save(update_fields=["asaas_customer_id"])
    return user.asaas_customer_id


def _fill_pix(payment: Payment) -> None:
    if payment.billing_type != "PIX" or payment.pix_payload:
        return
    try:
        qr = get_client().get_pix_qr_code(payment.external_id)
    except AsaasError:
        logger.info("QR Pix ainda indisponível para %s", payment.external_id)
        return
    payment.pix_payload = qr.get("payload", "")
    payment.pix_qr_image = qr.get("encodedImage", "")
    payment.save(update_fields=["pix_payload", "pix_qr_image", "updated_at"])


def register_provider_payment(data: dict, *, user, purpose: str, order=None, subscription=None) -> Payment:
    """Cria (ou recupera) o registro local de uma cobrança devolvida pelo Asaas."""
    payment, _ = Payment.objects.get_or_create(
        external_id=data["id"],
        defaults=dict(
            purpose=purpose,
            user=user,
            order=order,
            subscription=subscription,
            external_subscription_id=data.get("subscription") or "",
            billing_type=data.get("billingType", ""),
            status=data.get("status", "PENDING"),
            value_cents=value_to_cents(data.get("value", 0)),
            net_value_cents=value_to_cents(data["netValue"]) if data.get("netValue") is not None else None,
            due_date=date.fromisoformat(data["dueDate"]) if data.get("dueDate") else None,
            invoice_url=data.get("invoiceUrl") or "",
            bank_slip_url=data.get("bankSlipUrl") or "",
        ),
    )
    if subscription is not None and payment.cycle_id is None:
        from apps.subscriptions.services import get_or_create_cycle_for_payment

        get_or_create_cycle_for_payment(payment)
    _fill_pix(payment)
    return payment


def create_order_payment(order) -> Payment:
    existing = order.payments.exclude(status="DELETED").first()
    if existing:
        return existing
    customer = ensure_customer(order.user)
    due = date.today() + timedelta(days=3 if order.billing_type == "BOLETO" else 1)
    data = get_client().create_payment(
        customer=customer, billing_type=order.billing_type, value_cents=order.total_cents, due_date=due,
        description=f"PetVila Club · pedido {order.number}", external_reference=f"order:{order.pk}",
    )
    return register_provider_payment(data, user=order.user, purpose=Payment.Purpose.ORDER, order=order)


# ---------------- Webhook ----------------


def _event_id(payload: dict) -> str:
    if payload.get("id"):
        return str(payload["id"])
    pay = payload.get("payment") or {}
    return f"{payload.get('event')}:{pay.get('id')}:{pay.get('status')}"


def _status_from_event(event_type: str, payment_data: dict) -> str:
    if event_type == "PAYMENT_DELETED":
        return "DELETED"
    if event_type == "PAYMENT_RESTORED":
        return payment_data.get("status") or "PENDING"
    return payment_data.get("status") or "PENDING"


def _resolve_unknown_payment(payment_data: dict) -> Payment | None:
    """Webhook pode chegar antes de gravarmos a resposta da API: resolve pelo externalReference."""
    from apps.orders.models import Order
    from apps.subscriptions.models import Subscription

    ref = payment_data.get("externalReference") or ""
    sub_id = payment_data.get("subscription")
    if sub_id:
        sub = Subscription.objects.filter(asaas_subscription_id=sub_id).first()
        if sub is None and ref.startswith("subscription:"):
            sub = Subscription.objects.filter(pk=ref.split(":", 1)[1]).first()
        if sub:
            return register_provider_payment(payment_data, user=sub.user, purpose=Payment.Purpose.SUBSCRIPTION, subscription=sub)
    if ref.startswith("order:"):
        order = Order.objects.filter(pk=ref.split(":", 1)[1]).first()
        if order:
            return register_provider_payment(payment_data, user=order.user, purpose=Payment.Purpose.ORDER, order=order)
    return None


def process_event(payload: dict) -> str:
    event_type = payload.get("event", "")
    event_id = _event_id(payload)
    payment_data = payload.get("payment") or {}
    try:
        with transaction.atomic():
            event = PaymentEvent.objects.create(external_event_id=event_id, event_type=event_type,
                                                payment_external_id=payment_data.get("id", ""), payload=payload)
    except IntegrityError:
        return "duplicate"
    try:
        result = _apply_event(event_type, payment_data)
        event.result = result
    except Exception as exc:  # registra e deixa para reprocessar pelo painel
        logger.exception("Falha ao processar evento %s", event_id)
        event.error = f"{exc.__class__.__name__}: {exc}"
        result = "error"
        raise_alert(OperationalAlert.Kind.INTEGRATION, f"Falha ao processar evento {event_type}",
                    detail=event.error, obj=event, dedupe_key=f"event-error:{event.pk}")
    event.processed_at = timezone.now()
    event.save(update_fields=["result", "error", "processed_at"])
    return result


def reprocess_event(event: PaymentEvent) -> str:
    payment_data = event.payload.get("payment") or {}
    result = _apply_event(event.event_type, payment_data)
    event.result = f"reprocessed:{result}"
    event.error = ""
    event.processed_at = timezone.now()
    event.save(update_fields=["result", "error", "processed_at"])
    return result


@transaction.atomic
def _apply_event(event_type: str, payment_data: dict) -> str:
    if not payment_data.get("id"):
        return "ignored:no_payment"
    payment = Payment.objects.select_for_update().filter(external_id=payment_data["id"]).first()
    if payment is None:
        _resolve_unknown_payment(payment_data)
        payment = Payment.objects.select_for_update().filter(external_id=payment_data["id"]).first()
    if payment is None:
        raise_alert(OperationalAlert.Kind.RECONCILIATION, f"Cobrança desconhecida {payment_data['id']}",
                    detail=f"Evento {event_type} sem pedido ou assinatura correspondente.",
                    dedupe_key=f"unknown-payment:{payment_data['id']}")
        return "unknown_payment"
    return apply_status(payment, _status_from_event(event_type, payment_data), payment_data)


def apply_status(payment: Payment, new_status: str, payment_data: dict | None = None) -> str:
    payment_data = payment_data or {}
    old_status = payment.status
    old_rank = STATUS_RANK.get(old_status, 0)
    new_rank = STATUS_RANK.get(new_status, 0)
    payment.last_event_at = timezone.now()

    if "value" in payment_data:
        reported = value_to_cents(payment_data["value"])
        if reported != payment.value_cents:
            raise_alert(OperationalAlert.Kind.RECONCILIATION, f"Valor divergente na cobrança {payment.external_id}",
                        detail=f"Esperado {payment.value_cents}, provedor informou {reported}.", obj=payment,
                        dedupe_key=f"value-mismatch:{payment.external_id}:{reported}")
    if payment_data.get("netValue") is not None:
        payment.net_value_cents = value_to_cents(payment_data["netValue"])

    if new_status != old_status and new_rank < old_rank:
        payment.save(update_fields=["last_event_at", "net_value_cents", "updated_at"])
        return f"ignored:late_event({new_status}<{old_status})"
    needs_release = new_status in PAID_STATUSES and payment.confirmed_at is None
    if new_status == old_status and not needs_release:
        payment.save(update_fields=["last_event_at", "net_value_cents", "updated_at"])
        return "noop"

    payment.status = new_status
    payment.save()

    if new_status in PAID_STATUSES and payment.confirmed_at is None:
        payment.confirmed_at = timezone.now()
        payment.save(update_fields=["confirmed_at"])
        _on_paid(payment)
        return "paid"
    if new_status == "OVERDUE":
        _on_overdue(payment)
        return "overdue"
    if new_status == "REFUNDED":
        payment.refunded_cents = payment.value_cents
        payment.save(update_fields=["refunded_cents"])
        _on_refunded(payment)
        return "refunded"
    if new_status == "DELETED":
        _on_deleted(payment)
        return "deleted"
    if new_status.startswith("CHARGEBACK"):
        raise_alert(OperationalAlert.Kind.RECONCILIATION, f"Contestação na cobrança {payment.external_id}",
                    obj=payment, dedupe_key=f"chargeback:{payment.external_id}")
    return f"status:{new_status}"


def _on_paid(payment: Payment) -> None:
    if payment.order_id:
        from apps.orders.services import mark_order_paid

        mark_order_paid(payment.order_id, payment)
    elif payment.subscription_id:
        from apps.subscriptions.services import on_cycle_paid

        on_cycle_paid(payment)


def _on_overdue(payment: Payment) -> None:
    if payment.subscription_id:
        from apps.subscriptions.services import on_cycle_overdue

        on_cycle_overdue(payment)


def _on_refunded(payment: Payment) -> None:
    if payment.order_id:
        from apps.orders.models import Order

        Order.objects.filter(pk=payment.order_id).update(status=Order.Status.REFUNDED)


def _on_deleted(payment: Payment) -> None:
    if payment.order_id:
        from apps.orders.services import cancel_unpaid_order

        cancel_unpaid_order(payment.order_id, reason="Cobrança cancelada no provedor")
    elif payment.cycle_id:
        from apps.subscriptions.models import Cycle

        Cycle.objects.filter(pk=payment.cycle_id, status__in=[Cycle.Status.AWAITING_PAYMENT, Cycle.Status.PAYMENT_FAILED]).update(
            status=Cycle.Status.CANCELED
        )


# ---------------- Estornos ----------------


def request_refund(payment: Payment, value_cents: int, *, actor, reason: str, key: str) -> Refund:
    require_role(actor, Roles.FINANCEIRO, Roles.GESTOR)
    if not reason.strip():
        raise DomainError("Estorno exige motivo.")
    if value_cents <= 0:
        raise DomainError("Valor de estorno inválido.")
    existing = Refund.objects.filter(idempotency_key=key).first()
    if existing:
        return existing
    if not has_role(actor, Roles.GESTOR):
        limit = int(get_setting("refund_limit_cents_financeiro"))
        if value_cents > limit:
            raise DomainError(f"Estorno acima da alçada do financeiro ({limit / 100:.2f}). Solicite a um gestor.", code="over_limit")
    with transaction.atomic():
        locked = Payment.objects.select_for_update().get(pk=payment.pk)
        if not locked.is_paid and locked.status != "REFUNDED":
            raise DomainError("Só é possível estornar cobrança paga.")
        captured = locked.value_cents
        pending = sum(r.value_cents for r in locked.refunds.filter(status=Refund.Status.REQUESTED))
        if locked.refunded_cents + pending + value_cents > captured:
            raise DomainError("O total devolvido não pode superar o valor capturado.", code="refund_exceeds_capture")
        refund = Refund.objects.create(payment=locked, value_cents=value_cents, reason=reason, idempotency_key=key,
                                       requested_by=actor)
    try:
        get_client().refund_payment(payment.external_id, value_cents, reason)
    except AsaasError as exc:
        refund.status = Refund.Status.FAILED
        refund.error = str(exc)
        refund.save(update_fields=["status", "error", "updated_at"])
        raise_alert(OperationalAlert.Kind.RECONCILIATION, f"Falha no estorno da cobrança {payment.external_id}",
                    detail=str(exc), obj=refund)
        raise DomainError(f"O provedor recusou o estorno: {exc}", status_code=502) from exc
    with transaction.atomic():
        locked = Payment.objects.select_for_update().get(pk=payment.pk)
        locked.refunded_cents += value_cents
        locked.save(update_fields=["refunded_cents", "updated_at"])
        refund.status = Refund.Status.DONE
        refund.save(update_fields=["status", "updated_at"])
    audit(actor, "refund_executed", refund, reason=reason, changes={"value_cents": value_cents})
    return refund
