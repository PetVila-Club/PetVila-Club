"""Checkout da loja avulsa (CHK-01/02/03, LOJ-02, EST-01)."""

from __future__ import annotations

from datetime import timedelta

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.core.exceptions import ConflictError, DomainError
from apps.core.models import OperationalAlert
from apps.core.services import audit, get_setting, raise_alert
from apps.inventory import services as stock
from apps.payments.asaas import AsaasError

from .models import Order, OrderLine
from .pricing import build_quote

# Compra avulsa da loja: cartão de crédito ou Pix (regra de 13/11/2026; boleto saiu).
BILLING_TYPES = {"PIX", "CREDIT_CARD"}
STORE_TERMS_VERSION = "2026-11-01"


def checkout_store(user, *, items: list[dict], address_id: int, billing_type: str, expected_total_cents: int,
                   accept_terms: bool, idempotency_key: str, ip: str = "", subscription_key: str = "") -> Order:
    if not idempotency_key or len(idempotency_key) > 120:
        raise DomainError("Chave de idempotência ausente ou inválida.")
    existing = Order.objects.filter(user=user, idempotency_key=idempotency_key).first()
    if existing:
        return existing  # CHK-03: repetir a solicitação não cria nova compra
    if billing_type not in BILLING_TYPES:
        raise DomainError("Na loja, o pagamento é por cartão de crédito ou Pix.", code="billing_not_allowed")
    if not accept_terms:
        raise DomainError("É preciso aceitar as condições da compra.")
    if not user.cpf:
        raise DomainError("Informe seu CPF em Minha Vila > Meus dados para concluir o pagamento.", code="cpf_required")
    address = user.addresses.filter(pk=address_id).first()
    if address is None:
        raise DomainError("Endereço não encontrado.")

    quote = build_quote(user, items, address.cep_digits, subscription_key=subscription_key)
    if quote.problems:
        raise ConflictError(" ".join(quote.problems), code="quote_problems", data={"quote": quote.as_dict()})
    if quote.total_cents != expected_total_cents:
        # LOJ-02: total mudou (ex.: perdeu elegibilidade de assinante). Exige ciência antes de cobrar.
        raise ConflictError("Os valores foram atualizados. Confira o novo total antes de confirmar.",
                            code="total_changed", data={"quote": quote.as_dict()})

    try:
        with transaction.atomic():
            order = Order.objects.create(
                user=user,
                subtotal_cents=quote.subtotal_cents,
                discount_cents=quote.discount_cents,
                shipping_cents=quote.shipping_cents,
                total_cents=quote.total_cents,
                member_pricing=quote.member_pricing,
                shipping_address=address.snapshot(),
                shipping_zone=quote.zone.name if quote.zone else "",
                eta_days=quote.eta_days,
                billing_type=billing_type,
                accepted_terms={"version": STORE_TERMS_VERSION, "accepted_at": timezone.now().isoformat(), "ip": ip,
                                "member_via_subscription": subscription_key or None},
                idempotency_key=idempotency_key,
                expires_at=timezone.now() + timedelta(hours=int(get_setting("store_order_expiration_hours"))),
            )
            for line in quote.lines:
                ol = OrderLine.objects.create(
                    order=order, sku=line.sku, sku_code=line.sku.code, product_name=line.sku.product.name,
                    variant_name=line.sku.variant_name, quantity=line.quantity, list_price_cents=line.list_price_cents,
                    unit_price_cents=line.unit_price_cents, unit_cost_cents=line.sku.cost_cents,
                )
                stock.reserve(line.sku, line.quantity, key=ol.reserve_key, reference=order, reason=f"Pedido {order.number}")
    except IntegrityError:
        existing = Order.objects.filter(user=user, idempotency_key=idempotency_key).first()
        if existing:
            return existing
        raise

    audit(user, "order_created", order, changes={"total_cents": order.total_cents})
    from apps.payments.services import create_order_payment

    try:
        create_order_payment(order)
    except (AsaasError, DomainError) as exc:
        cancel_unpaid_order(order.pk, reason="Falha ao gerar cobrança")
        message = exc.message if isinstance(exc, DomainError) else str(exc)
        raise DomainError(f"Não conseguimos gerar a cobrança agora: {message}. Nenhum valor foi cobrado.",
                          code="payment_creation_failed", status_code=502) from exc
    return order


@transaction.atomic
def mark_order_paid(order_id: int, payment) -> None:
    order = Order.objects.select_for_update().get(pk=order_id)
    if order.paid_at is not None:
        return  # liberação única
    if order.status == Order.Status.CANCELED:
        # Pagamento tardio de pedido já cancelado/reserva liberada: decisão humana (reativar ou estornar).
        raise_alert(OperationalAlert.Kind.RECONCILIATION, f"Pagamento recebido para pedido cancelado {order.number}",
                    detail="Reativar com nova reserva ou estornar.", obj=order, dedupe_key=f"paid-canceled:{order.pk}")
        return
    order.status = Order.Status.PAID
    order.paid_at = timezone.now()
    order.save(update_fields=["status", "paid_at", "updated_at"])
    from apps.logistics.services import create_shipment_for_order

    create_shipment_for_order(order)


def cancel_unpaid_order(order_id: int, *, reason: str, actor=None) -> bool:
    with transaction.atomic():
        order = Order.objects.select_for_update().get(pk=order_id)
        if order.status != Order.Status.PENDING_PAYMENT:
            return False
        order.status = Order.Status.CANCELED
        order.canceled_at = timezone.now()
        order.save(update_fields=["status", "canceled_at", "updated_at"])
        for line in order.lines.all():
            stock.release(line.reserve_key, actor=actor, reason=reason)
    audit(actor, "order_canceled", order, reason=reason)
    return True


def expire_unpaid_orders() -> int:
    from apps.payments.asaas import get_client

    count = 0
    for order in Order.objects.filter(status=Order.Status.PENDING_PAYMENT, expires_at__lt=timezone.now()):
        for payment in order.payments.filter(status__in=["PENDING", "OVERDUE"]):
            try:
                get_client().delete_payment(payment.external_id)
            except AsaasError:
                pass
        if cancel_unpaid_order(order.pk, reason="Pedido expirado sem pagamento"):
            count += 1
    return count
