"""Assinaturas de kit e ração (ASS-01/02/03, PET-03, RAC-01/02)."""

from __future__ import annotations

import calendar
from datetime import date, timedelta

from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from apps.catalog.models import SKU
from apps.core.exceptions import ConflictError, DomainError
from apps.core.models import OperationalAlert
from apps.core.services import audit, get_setting, raise_alert
from apps.orders.models import ShippingZone
from apps.payments.asaas import AsaasError, get_client
from apps.plans.models import Plan

from .models import Cycle, Subscription, SubscriptionEvent

OPEN_STATUSES = [Subscription.Status.PENDING, Subscription.Status.ACTIVE, Subscription.Status.PAST_DUE, Subscription.Status.PAUSED]
FOOD_FREQUENCIES = {30: "MONTHLY", 60: "BIMONTHLY"}
SUBSCRIPTION_TERMS_VERSION = "2026-11-01"


def add_months(d: date, months: int) -> date:
    month = d.month - 1 + months
    year = d.year + month // 12
    month = month % 12 + 1
    day = min(d.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def next_billing_after(sub: Subscription, billing: date) -> date:
    if sub.kind == Subscription.Kind.KIT:
        return add_months(billing, 1)
    return billing + timedelta(days=sub.frequency_days)


def cutoff_for(billing: date) -> date:
    return billing - timedelta(days=int(get_setting("cutoff_days_before_billing")))


def log_event(sub: Subscription, kind: str, actor=None, **detail) -> None:
    SubscriptionEvent.objects.create(subscription=sub, kind=kind, actor=actor, detail=detail)


def _check_address(user, address_id: int):
    address = user.addresses.filter(pk=address_id).first()
    if address is None:
        raise DomainError("Endereço não encontrado.")
    if ShippingZone.for_cep(address.cep_digits) is None:
        raise DomainError("Ainda não entregamos neste CEP. Estamos ampliando as regiões atendidas.", code="cep_not_served")
    return address


def _start_provider_subscription(sub: Subscription, description: str, cycle: str) -> None:
    from apps.payments.models import Payment
    from apps.payments.services import ensure_customer, register_provider_payment

    customer = ensure_customer(sub.user)
    client = get_client()
    try:
        data = client.create_subscription(
            customer=customer, billing_type=sub.billing_type, value_cents=sub.total_per_cycle_cents,
            next_due_date=date.today(), cycle=cycle, description=description, external_reference=f"subscription:{sub.pk}",
        )
    except AsaasError as exc:
        log_event(sub, "provider_error", error=str(exc))
        raise DomainError(f"Não conseguimos criar a cobrança recorrente: {exc}. Nada foi cobrado.",
                          code="provider_error", status_code=502) from exc
    sub.asaas_subscription_id = data["id"]
    sub.next_billing_date = date.today()
    sub.save(update_fields=["asaas_subscription_id", "next_billing_date", "updated_at"])
    log_event(sub, "provider_subscription_created", provider_id=data["id"])
    try:
        for payment_data in client.list_subscription_payments(data["id"])[:1]:
            register_provider_payment(payment_data, user=sub.user, purpose=Payment.Purpose.SUBSCRIPTION, subscription=sub)
    except AsaasError:
        pass  # a primeira cobrança chega também pelo webhook PAYMENT_CREATED


def contract_kits(user, *, plan_code: str, dog_ids: list[int], address_id: int, billing_type: str,
                  commitment_months: int | None, offer_id: int, accept_terms: bool, checkout_key: str,
                  ip: str = "") -> list[Subscription]:
    """J01/J02: um vínculo de assinatura por cão; o pedido pode agrupar vários vínculos."""
    if not accept_terms:
        raise DomainError("É preciso aceitar as condições da assinatura.")
    if billing_type not in Subscription.BillingType.values:
        raise DomainError("Meio de pagamento indisponível.")
    if not checkout_key:
        raise DomainError("Chave de idempotência ausente.")
    plan = Plan.objects.filter(code=plan_code, is_active=True).first()
    if plan is None:
        raise DomainError("Plano não encontrado.")
    offer = plan.current_offer()
    if offer is None or not offer.price_cents:
        raise DomainError(f"O {plan.name} ainda não está disponível para contratação.", code="offer_unavailable")
    if offer.pk != offer_id:
        raise ConflictError("As condições do plano foram atualizadas. Revise antes de confirmar.", code="offer_changed")
    if offer.commitment_options and commitment_months not in offer.commitment_options:
        raise DomainError("Escolha um ciclo de permanência válido.")
    if not dog_ids:
        raise DomainError("Selecione ao menos um cão.")
    dogs = list(user.dogs.filter(pk__in=dog_ids, is_active=True))
    if len(dogs) != len(set(dog_ids)):
        raise DomainError("Cão não encontrado.")
    address = _check_address(user, address_id)

    # Retomada idempotente da mesma contratação
    existing = list(Subscription.objects.filter(user=user, checkout_key=checkout_key, kind=Subscription.Kind.KIT))
    if existing and all(s.asaas_subscription_id for s in existing) and len(existing) == len(dogs):
        return existing

    for dog in dogs:
        clash = Subscription.objects.filter(dog=dog, kind=Subscription.Kind.KIT, status__in=OPEN_STATUSES).exclude(
            checkout_key=checkout_key
        )
        if clash.exists():
            raise DomainError(f"{dog.name} já tem uma assinatura de kit em andamento.", code="dog_already_subscribed")

    accepted = {
        "terms_version": SUBSCRIPTION_TERMS_VERSION,
        "offer": offer.snapshot(),
        "commitment_months": commitment_months,
        "accepted_at": timezone.now().isoformat(),
        "ip": ip,
        "text": f"Assinatura mensal {plan.name}, {commitment_months or '-'} meses, cobrança recorrente automática.",
    }
    subs = []
    for dog in dogs:
        with transaction.atomic():
            sub, created = Subscription.objects.get_or_create(
                user=user, checkout_key=checkout_key, dog=dog, kind=Subscription.Kind.KIT,
                defaults=dict(
                    plan=plan, offer=offer, commitment_months=commitment_months, price_cents=offer.price_cents,
                    shipping_cents=offer.shipping_cents, billing_type=billing_type, shipping_address=address.snapshot(),
                    accepted_terms=accepted,
                ),
            )
            if created:
                log_event(sub, "contracted", actor=user, offer_version=offer.version)
                audit(user, "subscription_contracted", sub, changes={"offer": offer.pk, "dog": dog.pk})
        if not sub.asaas_subscription_id:
            _start_provider_subscription(sub, f"PetVila Club · {plan.name} · {dog.name}", "MONTHLY")
        subs.append(sub)
    return subs


def contract_food(user, *, sku_id: int, quantity: int, frequency_days: int, address_id: int, billing_type: str,
                  dog_id: int | None, expected_price_cents: int, accept_terms: bool, checkout_key: str,
                  ip: str = "") -> Subscription:
    """RAC-01: ração contratada sem depender de kit, com SKU e quantidade preservados."""
    if not accept_terms:
        raise DomainError("É preciso aceitar as condições da recorrência.")
    if billing_type not in Subscription.BillingType.values:
        raise DomainError("Meio de pagamento indisponível.")
    if frequency_days not in FOOD_FREQUENCIES:
        raise DomainError("Frequência indisponível.")
    if quantity < 1 or quantity > 10:
        raise DomainError("Quantidade inválida.")
    sku = SKU.objects.select_related("product").filter(pk=sku_id, is_active=True, product__is_recurring_food=True).first()
    if sku is None or not sku.price_cents:
        raise DomainError("Esta ração não está disponível para recorrência.")
    if sku.missing_sale_data():
        raise DomainError("Esta ração está temporariamente indisponível.")
    price = sku.price_cents * quantity
    if price != expected_price_cents:
        raise ConflictError("O valor da ração foi atualizado. Revise antes de confirmar.", code="total_changed",
                            data={"price_cents": price})
    dog = user.dogs.filter(pk=dog_id).first() if dog_id else None
    if dog_id and dog is None:
        raise DomainError("Cão não encontrado.")
    address = _check_address(user, address_id)
    zone = ShippingZone.for_cep(address.cep_digits)

    with transaction.atomic():
        sub, created = Subscription.objects.get_or_create(
            user=user, checkout_key=checkout_key, dog=dog, kind=Subscription.Kind.FOOD,
            defaults=dict(
                sku=sku, quantity=quantity, frequency_days=frequency_days, price_cents=price,
                shipping_cents=zone.price_cents if zone else 0, billing_type=billing_type,
                shipping_address=address.snapshot(),
                accepted_terms={
                    "terms_version": SUBSCRIPTION_TERMS_VERSION, "sku": sku.snapshot(), "quantity": quantity,
                    "frequency_days": frequency_days, "price_cents": price, "accepted_at": timezone.now().isoformat(),
                    "ip": ip, "text": "Recorrência de ração sem troca automática de marca ou fórmula.",
                },
            ),
        )
        if created:
            log_event(sub, "contracted", actor=user)
            audit(user, "food_subscription_contracted", sub)
    if not sub.asaas_subscription_id:
        _start_provider_subscription(sub, f"PetVila Club · Ração {sku.display_name}", FOOD_FREQUENCIES[frequency_days])
    return sub


# ---------------- Ciclos a partir de cobranças ----------------


def get_or_create_cycle_for_payment(payment) -> Cycle:
    """Uma cobrança gera no máximo um ciclo (ASS-01)."""
    with transaction.atomic():
        sub = Subscription.objects.select_for_update().get(pk=payment.subscription_id)
        cycle = Cycle.objects.filter(external_payment_id=payment.external_id).first()
        if cycle is None:
            number = (sub.cycles.aggregate(m=Max("number"))["m"] or 0) + 1
            billing = payment.due_date or date.today()
            cycle = Cycle.objects.create(
                subscription=sub, number=number, billing_date=billing, cutoff_date=cutoff_for(billing),
                price_cents=sub.price_cents, shipping_cents=sub.shipping_cents,
                offer_snapshot=sub.offer.snapshot() if sub.offer else sub.accepted_terms,
                external_payment_id=payment.external_id,
            )
        if payment.cycle_id != cycle.pk:
            type(payment).objects.filter(pk=payment.pk).update(cycle=cycle)
            payment.cycle = cycle
    return cycle


def on_cycle_paid(payment) -> None:
    cycle = payment.cycle or get_or_create_cycle_for_payment(payment)
    with transaction.atomic():
        cycle = Cycle.objects.select_for_update().get(pk=cycle.pk)
        sub = Subscription.objects.select_for_update().get(pk=cycle.subscription_id)
        if cycle.paid_at is not None:
            return
        cycle.paid_at = timezone.now()
        if cycle.status in (Cycle.Status.AWAITING_PAYMENT, Cycle.Status.PAYMENT_FAILED):
            cycle.status = Cycle.Status.PAID
        cycle.save(update_fields=["paid_at", "status", "updated_at"])
        if sub.status in (Subscription.Status.PENDING, Subscription.Status.PAST_DUE):
            sub.status = Subscription.Status.ACTIVE
        if sub.started_at is None:
            sub.started_at = timezone.now()
        sub.next_billing_date = next_billing_after(sub, cycle.billing_date or date.today())
        sub.save(update_fields=["status", "started_at", "next_billing_date", "updated_at"])
        log_event(sub, "cycle_paid", cycle=cycle.code)
    if sub.kind == Subscription.Kind.FOOD:
        from apps.logistics.services import create_shipment_for_food_cycle

        create_shipment_for_food_cycle(cycle)


def on_cycle_overdue(payment) -> None:
    """ASS-03: cobrança recusada/vencida mantém o ciclo não liberado."""
    with transaction.atomic():
        sub = Subscription.objects.select_for_update().get(pk=payment.subscription_id)
        if payment.cycle_id:
            Cycle.objects.filter(pk=payment.cycle_id, paid_at__isnull=True).update(status=Cycle.Status.PAYMENT_FAILED)
        if sub.status == Subscription.Status.ACTIVE:
            sub.status = Subscription.Status.PAST_DUE
            sub.save(update_fields=["status", "updated_at"])
        log_event(sub, "payment_overdue", payment=payment.external_id)
    raise_alert(OperationalAlert.Kind.PAYMENT, f"Cobrança vencida da assinatura {sub.number}", obj=sub,
                dedupe_key=f"overdue:{payment.external_id}")


# ---------------- Alterações (ASS-02, RAC-02) ----------------


def cancel_subscription(sub: Subscription, *, actor, reason: str = "") -> dict:
    """H07: antes do corte, nenhuma cobrança futura; depois do corte, o ciclo já processado é entregue."""
    if sub.status in (Subscription.Status.CANCELED, Subscription.Status.ENDED):
        return {"effective_date": sub.cancel_effective_date, "message": "Esta assinatura já está cancelada."}
    today = date.today()
    client = get_client()
    before_cutoff = sub.next_billing_date is None or today < cutoff_for(sub.next_billing_date) or sub.status == Subscription.Status.PENDING

    with transaction.atomic():
        sub = Subscription.objects.select_for_update().get(pk=sub.pk)
        sub.cancel_requested_at = timezone.now()
        if before_cutoff:
            if sub.asaas_subscription_id:
                try:
                    client.cancel_subscription(sub.asaas_subscription_id)
                except AsaasError as exc:
                    raise DomainError(f"O provedor não confirmou o cancelamento: {exc}. Tente novamente.", status_code=502) from exc
            sub.status = Subscription.Status.CANCELED
            sub.cancel_effective_date = today
            sub.cycles.filter(status=Cycle.Status.AWAITING_PAYMENT).update(status=Cycle.Status.CANCELED)
            message = "Assinatura cancelada. Nenhuma nova cobrança será feita. Ciclos já pagos serão entregues."
        else:
            effective = sub.next_billing_date
            if sub.asaas_subscription_id:
                try:
                    client.update_subscription(sub.asaas_subscription_id, endDate=effective.isoformat())
                except AsaasError as exc:
                    raise DomainError(f"O provedor não confirmou o cancelamento: {exc}. Tente novamente.", status_code=502) from exc
            sub.cancel_effective_date = effective
            message = (
                f"Cancelamento registrado. O ciclo de {effective:%d/%m/%Y} já passou da data de corte e será cobrado e "
                "entregue normalmente; depois dele, nenhuma nova cobrança."
            )
        sub.save()
        log_event(sub, "canceled", actor=actor, reason=reason, effective=str(sub.cancel_effective_date))
    audit(actor, "subscription_canceled", sub, reason=reason, changes={"effective_date": str(sub.cancel_effective_date)})
    return {"effective_date": sub.cancel_effective_date, "message": message}


def pause_subscription(sub: Subscription, *, actor, reason: str = "") -> dict:
    if sub.status != Subscription.Status.ACTIVE:
        raise DomainError("Só assinaturas ativas podem ser pausadas.")
    assisted = False
    try:
        if sub.asaas_subscription_id:
            get_client().update_subscription(sub.asaas_subscription_id, status="INACTIVE")
    except AsaasError:
        assisted = True
        raise_alert(OperationalAlert.Kind.PAYMENT, f"Pausar cobrança no Asaas: {sub.number}",
                    detail="O provedor não aceitou a pausa automática. Execute no painel do Asaas e registre.", obj=sub)
    sub.status = Subscription.Status.PAUSED
    sub.paused_at = timezone.now()
    sub.save(update_fields=["status", "paused_at", "updated_at"])
    log_event(sub, "paused", actor=actor, reason=reason, assisted=assisted)
    audit(actor, "subscription_paused", sub, reason=reason)
    return {"message": "Assinatura pausada. Outras assinaturas seguem normalmente." + (
        " A pausa da cobrança será confirmada pela nossa equipe." if assisted else "")}


def resume_subscription(sub: Subscription, *, actor) -> dict:
    if sub.status != Subscription.Status.PAUSED:
        raise DomainError("Esta assinatura não está pausada.")
    next_date = max(date.today() + timedelta(days=1), sub.next_billing_date or date.today())
    try:
        if sub.asaas_subscription_id:
            get_client().update_subscription(sub.asaas_subscription_id, status="ACTIVE", nextDueDate=next_date.isoformat())
    except AsaasError:
        raise_alert(OperationalAlert.Kind.PAYMENT, f"Retomar cobrança no Asaas: {sub.number}", obj=sub)
    sub.status = Subscription.Status.ACTIVE
    sub.paused_at = None
    sub.next_billing_date = next_date
    sub.save(update_fields=["status", "paused_at", "next_billing_date", "updated_at"])
    log_event(sub, "resumed", actor=actor)
    audit(actor, "subscription_resumed", sub)
    return {"message": f"Assinatura retomada. Próxima cobrança em {next_date:%d/%m/%Y}."}


def apply_scheduled_cancellations() -> int:
    today = date.today()
    qs = Subscription.objects.filter(cancel_effective_date__lt=today, status__in=OPEN_STATUSES)
    count = 0
    for sub in qs:
        sub.status = Subscription.Status.CANCELED
        sub.save(update_fields=["status", "updated_at"])
        log_event(sub, "cancellation_effective")
        count += 1
    return count
