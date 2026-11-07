"""Separação, conferência, expedição, entrega e ocorrências (LOG-01/02/03, EST-02, FIS-01)."""

from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from apps.catalog.models import SKU
from apps.core.exceptions import DomainError
from apps.core.models import OperationalAlert
from apps.core.services import Roles, audit, get_setting, raise_alert, require_role
from apps.fiscal.models import FiscalDocument
from apps.inventory import services as stock

from .models import Incident, Shipment, ShipmentLine


def _with_fiscal(shipment: Shipment, amount_cents: int) -> Shipment:
    FiscalDocument.objects.get_or_create(shipment=shipment, defaults={"amount_cents": amount_cents})
    return shipment


@transaction.atomic
def create_shipment_for_order(order) -> Shipment:
    shipment, created = Shipment.objects.get_or_create(
        order=order, resend_of=None,
        defaults={"kind": Shipment.Kind.STORE, "user": order.user, "shipping_address": order.shipping_address},
    )
    if created:
        for line in order.lines.select_related("sku__product"):
            ShipmentLine.objects.create(shipment=shipment, sku=line.sku, sku_code=line.sku_code,
                                        product_name=line.sku.display_name, quantity=line.quantity, order_line=line,
                                        reserve_key=line.reserve_key)
        _with_fiscal(shipment, order.total_cents)
    return shipment


@transaction.atomic
def create_shipment_for_kit(kit) -> Shipment:
    cycle = kit.cycle
    sub = cycle.subscription
    shipment, created = Shipment.objects.get_or_create(
        cycle=cycle, resend_of=None,
        defaults={"kind": Shipment.Kind.KIT, "user": sub.user, "shipping_address": sub.shipping_address},
    )
    if created:
        _kit_lines(shipment, kit)
        _with_fiscal(shipment, cycle.price_cents + cycle.shipping_cents)
    return shipment


def _kit_lines(shipment: Shipment, kit) -> None:
    for line in kit.active_lines.select_related("sku__product"):
        ShipmentLine.objects.create(shipment=shipment, sku=line.sku, sku_code=line.sku.code, product_name=line.sku.display_name,
                                    quantity=line.quantity, dog=kit.dog, kit_line=line, reserve_key=line.reserve_key)


@transaction.atomic
def sync_kit_shipment_lines(kit) -> None:
    shipment = Shipment.objects.filter(cycle=kit.cycle, resend_of=None).first()
    if shipment is None:
        return
    if shipment.status in (Shipment.Status.SHIPPED, Shipment.Status.DELIVERED):
        raise DomainError("Expedição já realizada; o conteúdo não pode mais ser alterado.")
    shipment.lines.all().delete()
    _kit_lines(shipment, kit)
    shipment.status = Shipment.Status.PENDING
    shipment.divergences = []
    shipment.save(update_fields=["status", "divergences", "updated_at"])


def create_shipment_for_food_cycle(cycle) -> Shipment | None:
    """RAC-02: na falta da ração, aviso e decisão registrada; nunca troca automática de marca ou fórmula."""
    sub = cycle.subscription
    key = f"foodcycle:{cycle.pk}:reserve"
    try:
        with transaction.atomic():
            stock.reserve(sub.sku, sub.quantity, key=key, reference=cycle, reason=f"Ração {cycle.code}")
            shipment, created = Shipment.objects.get_or_create(
                cycle=cycle, resend_of=None,
                defaults={"kind": Shipment.Kind.FOOD, "user": sub.user, "shipping_address": sub.shipping_address},
            )
            if created:
                ShipmentLine.objects.create(shipment=shipment, sku=sub.sku, sku_code=sub.sku.code,
                                            product_name=sub.sku.display_name, quantity=sub.quantity, dog=sub.dog,
                                            reserve_key=key)
                _with_fiscal(shipment, cycle.price_cents + cycle.shipping_cents)
            type(cycle).objects.filter(pk=cycle.pk).update(status="reserved")
            return shipment
    except stock.InsufficientStock as exc:
        raise_alert(OperationalAlert.Kind.STOCKOUT, f"Falta de ração para {cycle.code}",
                    detail=f"{exc.message} Avisar o tutor e registrar decisão. Não enviar outra marca ou fórmula.",
                    obj=cycle, dedupe_key=f"food-stockout:{cycle.pk}")
        return None


def start_picking(shipment: Shipment, *, actor) -> Shipment:
    require_role(actor, Roles.OPERACAO, Roles.GESTOR)
    if shipment.status not in (Shipment.Status.PENDING, Shipment.Status.DIVERGENT):
        raise DomainError("Esta expedição não está aguardando separação.")
    shipment.status = Shipment.Status.PICKING
    shipment.save(update_fields=["status", "updated_at"])
    audit(actor, "picking_started", shipment)
    return shipment


def expected_counts(shipment: Shipment) -> dict[str, int]:
    counts: dict[str, int] = {}
    for line in shipment.lines.all():
        counts[line.sku_code] = counts.get(line.sku_code, 0) + line.quantity
    return counts


@transaction.atomic
def check_shipment(shipment: Shipment, counted: dict[str, int], *, actor) -> list[dict]:
    """Conferência: identifica falta, excesso ou SKU diferente."""
    require_role(actor, Roles.OPERACAO, Roles.GESTOR)
    shipment = Shipment.objects.select_for_update().get(pk=shipment.pk)
    if shipment.status not in (Shipment.Status.PICKING, Shipment.Status.DIVERGENT, Shipment.Status.PENDING):
        raise DomainError("Expedição fora da etapa de conferência.")
    expected = expected_counts(shipment)
    divergences = []
    for code in sorted(set(expected) | set(counted)):
        exp, got = expected.get(code, 0), int(counted.get(code, 0))
        if exp == got:
            continue
        if exp == 0:
            kind = "sku_diferente"
        elif got < exp:
            kind = "falta"
        else:
            kind = "excesso"
        divergences.append({"sku": code, "expected": exp, "counted": got, "kind": kind})
    shipment.divergences = divergences
    shipment.checked_by = actor
    shipment.status = Shipment.Status.DIVERGENT if divergences else Shipment.Status.CHECKED
    shipment.save(update_fields=["divergences", "checked_by", "status", "updated_at"])
    audit(actor, "shipment_checked", shipment, changes={"divergences": divergences})
    return divergences


@transaction.atomic
def register_label(shipment: Shipment, *, carrier: str, tracking_code: str, actor, service: str = "",
                   tracking_url: str = "") -> Shipment:
    """Falha na etiqueta permite retomar sem contratar dois envios: registro é único por expedição."""
    require_role(actor, Roles.OPERACAO, Roles.GESTOR)
    shipment = Shipment.objects.select_for_update().get(pk=shipment.pk)
    if shipment.label_registered_at:
        if shipment.tracking_code != tracking_code:
            raise DomainError(f"Esta expedição já tem etiqueta ({shipment.tracking_code}). Cancele-a antes de gerar outra.")
        return shipment
    shipment.carrier, shipment.tracking_code = carrier, tracking_code
    shipment.service, shipment.tracking_url = service, tracking_url
    shipment.label_registered_at = timezone.now()
    shipment.save()
    audit(actor, "label_registered", shipment, changes={"carrier": carrier, "tracking": tracking_code})
    return shipment


def fiscal_ok(shipment: Shipment) -> tuple[bool, str]:
    if not get_setting("fiscal_required_for_shipping"):
        return True, ""
    docs = list(shipment.fiscal_documents.all())
    if any(d.status in (FiscalDocument.Status.AUTHORIZED, FiscalDocument.Status.NOT_REQUIRED) for d in docs):
        return True, ""
    if any(d.status == FiscalDocument.Status.REJECTED for d in docs):
        return False, "Documento fiscal rejeitado: corrija e reemita antes de expedir."
    return False, "Documento fiscal ainda não autorizado."


def ship(shipment: Shipment, *, actor) -> Shipment:
    require_role(actor, Roles.OPERACAO, Roles.GESTOR)
    with transaction.atomic():
        shipment = Shipment.objects.select_for_update().get(pk=shipment.pk)
        if shipment.status == Shipment.Status.SHIPPED:
            return shipment  # repetição não baixa estoque de novo
        if shipment.status != Shipment.Status.CHECKED:
            raise DomainError("A expedição só libera conteúdo conferido e sem divergência.", code="not_checked")
        ok, reason = fiscal_ok(shipment)
        if not ok:
            raise DomainError(reason, code="fiscal_blocked")
        if not shipment.tracking_code:
            raise DomainError("Registre transportador e rastreio (ou registro equivalente) antes de expedir.")
        for line in shipment.lines.select_related("sku"):
            lot = stock.pick_lot(line.sku, line.quantity, min_valid_days=7)
            stock.ship(line.reserve_key, actor=actor, lot=lot, reason=f"Expedição {shipment.number}")
            if lot:
                line.lot = lot
                line.save(update_fields=["lot"])
        shipment.status = Shipment.Status.SHIPPED
        shipment.shipped_at = timezone.now()
        shipment.save(update_fields=["status", "shipped_at", "updated_at"])
        _propagate(shipment, "shipped")
    audit(actor, "shipment_shipped", shipment)
    return shipment


def mark_delivered(shipment: Shipment, *, actor, source: str = "carrier") -> Shipment:
    require_role(actor, Roles.OPERACAO, Roles.ATENDIMENTO, Roles.GESTOR)
    with transaction.atomic():
        shipment = Shipment.objects.select_for_update().get(pk=shipment.pk)
        if shipment.status == Shipment.Status.DELIVERED:
            return shipment
        if shipment.status not in (Shipment.Status.SHIPPED, Shipment.Status.EXCEPTION):
            raise DomainError("Só expedições enviadas podem ser marcadas como entregues.")
        shipment.status = Shipment.Status.DELIVERED
        shipment.delivered_at = timezone.now()
        shipment.delivery_source = source
        shipment.save(update_fields=["status", "delivered_at", "delivery_source", "updated_at"])
        _propagate(shipment, "delivered")
    audit(actor, "shipment_delivered", shipment, changes={"source": source})
    return shipment


def _propagate(shipment: Shipment, status: str) -> None:
    if shipment.resend_of_id:
        return
    if shipment.order_id:
        from apps.orders.models import Order

        Order.objects.filter(pk=shipment.order_id).update(status=status)
    if shipment.cycle_id:
        from apps.subscriptions.models import Cycle

        Cycle.objects.filter(pk=shipment.cycle_id).update(status=status)


def open_incident(shipment: Shipment, *, kind: str, source: str, description: str, actor) -> Incident:
    require_role(actor, Roles.OPERACAO, Roles.ATENDIMENTO, Roles.GESTOR)
    incident = Incident.objects.create(shipment=shipment, kind=kind, source=source, description=description, created_by=actor)
    if kind in (Incident.Kind.LOST, Incident.Kind.DAMAGED, Incident.Kind.DELAY) and source == Incident.Source.CARRIER:
        Shipment.objects.filter(pk=shipment.pk, status=Shipment.Status.SHIPPED).update(status=Shipment.Status.EXCEPTION)
    audit(actor, "incident_opened", incident, reason=description)
    return incident


def create_resend(incident: Incident, items: list[tuple[SKU, int]], *, actor, reason: str) -> Shipment:
    """Reenvio vincula-se à entrega original, lista os novos SKUs e gera movimentação própria."""
    require_role(actor, Roles.OPERACAO, Roles.GESTOR)
    if not items:
        raise DomainError("Informe os itens do reenvio.")
    if incident.resend_id:
        return incident.resend
    original = incident.shipment
    with transaction.atomic():
        resend = Shipment.objects.create(kind=Shipment.Kind.RESEND, user=original.user, resend_of=original,
                                         order=original.order, cycle=original.cycle,
                                         shipping_address=original.shipping_address)
        dog = original.lines.exclude(dog=None).values_list("dog", flat=True).first()
        for sku, qty in items:
            key = f"resend:{resend.pk}:{sku.pk}:reserve"
            stock.reserve(sku, qty, key=key, reference=resend, actor=actor, reason=f"Reenvio de {original.number}")
            ShipmentLine.objects.create(shipment=resend, sku=sku, sku_code=sku.code, product_name=sku.display_name,
                                        quantity=qty, dog_id=dog, reserve_key=key)
        FiscalDocument.objects.create(shipment=resend)
        incident.resend = resend
        incident.save(update_fields=["resend", "updated_at"])
    audit(actor, "resend_created", resend, reason=reason, changes={"incident": incident.pk})
    return resend


def register_return(shipment: Shipment, sku: SKU, quantity: int, *, actor, reason: str) -> None:
    require_role(actor, Roles.OPERACAO, Roles.GESTOR)
    shipped = sum(line.quantity for line in shipment.lines.filter(sku=sku))
    if quantity > shipped:
        raise DomainError("Quantidade devolvida maior que a expedida.")
    stock.return_to_quarantine(sku, quantity, key=f"return:{shipment.pk}:{sku.pk}", actor=actor, reason=reason)
    audit(actor, "return_registered", shipment, reason=reason, changes={"sku": sku.code, "quantity": quantity})
