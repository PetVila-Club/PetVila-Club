"""
Estoque: toda operação trava a linha de saldo (SELECT ... FOR UPDATE) e usa uma
chave de idempotência, para que repetição de evento não reserve, libere ou baixe duas vezes.
"""

from __future__ import annotations

from datetime import date, timedelta

from django.db import transaction

from apps.catalog.models import SKU
from apps.core.exceptions import ConflictError, DomainError

from .models import Lot, StockLevel, StockMovement


class InsufficientStock(ConflictError):
    def __init__(self, sku: SKU, requested: int, available: int):
        super().__init__(
            f"Estoque insuficiente para {sku.display_name}: pedido {requested}, disponível {available}.",
            code="insufficient_stock",
            data={"sku": sku.code, "requested": requested, "available": available},
        )


def _lock_level(sku_id: int) -> StockLevel:
    level, _ = StockLevel.objects.get_or_create(sku_id=sku_id)
    return StockLevel.objects.select_for_update().get(pk=level.pk)


def _existing(key: str | None) -> StockMovement | None:
    if not key:
        return None
    return StockMovement.objects.filter(idempotency_key=key).first()


@transaction.atomic
def receive(sku: SKU, quantity: int, *, actor=None, lot_code: str = "", expires_on: date | None = None,
            storage: str = "", reason: str = "Entrada de mercadoria", key: str | None = None) -> StockMovement:
    if quantity <= 0:
        raise DomainError("Quantidade de entrada deve ser positiva.")
    if (found := _existing(key)) is not None:
        return found
    level = _lock_level(sku.pk)
    lot = None
    if lot_code:
        lot, created = Lot.objects.get_or_create(
            sku=sku, code=lot_code,
            defaults={"expires_on": expires_on, "received_on": date.today(), "quantity_received": quantity,
                      "quantity_remaining": quantity, "storage_conditions": storage},
        )
        if not created:
            lot.quantity_received += quantity
            lot.quantity_remaining += quantity
            lot.save(update_fields=["quantity_received", "quantity_remaining"])
    level.physical += quantity
    level.save(update_fields=["physical", "updated_at"])
    return StockMovement.objects.create(sku=sku, kind=StockMovement.Kind.ENTRY, quantity=quantity, lot=lot,
                                        reason=reason, actor=actor, idempotency_key=key)


@transaction.atomic
def reserve(sku: SKU, quantity: int, *, key: str, reference=None, actor=None, reason: str = "") -> StockMovement:
    """Reserva unidades disponíveis. Duas ordens concorrentes nunca reservam a mesma última unidade."""
    if (found := _existing(key)) is not None:
        return found
    level = _lock_level(sku.pk)
    if level.available < quantity:
        raise InsufficientStock(sku, quantity, level.available)
    level.reserved += quantity
    level.save(update_fields=["reserved", "updated_at"])
    return StockMovement.objects.create(
        sku=sku, kind=StockMovement.Kind.RESERVE, quantity=quantity, idempotency_key=key, actor=actor, reason=reason,
        reference_type=reference._meta.label if reference is not None else "",
        reference_id=str(reference.pk) if reference is not None else "",
    )


@transaction.atomic
def release(reserve_key: str, *, actor=None, reason: str = "") -> StockMovement | None:
    """Libera uma reserva uma única vez. Não libera reserva já baixada pela expedição."""
    reservation = _existing(reserve_key)
    if reservation is None:
        return None
    release_key = f"{reserve_key}:release"
    if (found := _existing(release_key)) is not None:
        return found
    if _existing(f"{reserve_key}:ship") is not None:
        return None
    level = _lock_level(reservation.sku_id)
    level.reserved = max(0, level.reserved - reservation.quantity)
    level.save(update_fields=["reserved", "updated_at"])
    return StockMovement.objects.create(
        sku_id=reservation.sku_id, kind=StockMovement.Kind.RELEASE, quantity=reservation.quantity,
        idempotency_key=release_key, actor=actor, reason=reason,
        reference_type=reservation.reference_type, reference_id=reservation.reference_id,
    )


def pick_lot(sku: SKU, quantity: int, min_valid_days: int = 0) -> Lot | None:
    """EST-02: saída pela validade mais próxima ainda apta."""
    if not sku.tracks_lots:
        return None
    limit = date.today() + timedelta(days=min_valid_days)
    lot = (
        Lot.objects.filter(sku=sku, is_blocked=False, quantity_remaining__gte=quantity)
        .exclude(expires_on__lt=limit)
        .order_by("expires_on", "received_on")
        .first()
    )
    if lot is None:
        raise DomainError(f"Nenhum lote apto (não vencido e com saldo) para {sku.display_name}.", code="no_valid_lot")
    return lot


@transaction.atomic
def ship(reserve_key: str, *, actor=None, lot: Lot | None = None, reason: str = "Expedição") -> StockMovement:
    """Baixa física: consome a reserva. Repetir a confirmação não baixa de novo (LOG-01)."""
    ship_key = f"{reserve_key}:ship"
    if (found := _existing(ship_key)) is not None:
        return found
    reservation = _existing(reserve_key)
    if reservation is None:
        raise DomainError("Não há reserva para este item; a expedição só libera conteúdo reservado.", code="not_reserved")
    if _existing(f"{reserve_key}:release") is not None:
        raise DomainError("A reserva deste item foi liberada; reserve novamente antes de expedir.", code="reservation_released")
    level = _lock_level(reservation.sku_id)
    level.reserved -= reservation.quantity
    level.physical -= reservation.quantity
    level.save(update_fields=["reserved", "physical", "updated_at"])
    if lot is not None:
        Lot.objects.filter(pk=lot.pk).update(quantity_remaining=max(0, lot.quantity_remaining - reservation.quantity))
    return StockMovement.objects.create(
        sku_id=reservation.sku_id, kind=StockMovement.Kind.SHIP, quantity=reservation.quantity, lot=lot,
        idempotency_key=ship_key, actor=actor, reason=reason,
        reference_type=reservation.reference_type, reference_id=reservation.reference_id,
    )


@transaction.atomic
def adjust(sku: SKU, delta: int, *, actor, reason: str) -> StockMovement:
    """Ajuste manual exige motivo e responsável."""
    if not reason.strip() or actor is None:
        raise DomainError("Ajuste de estoque exige motivo e responsável.")
    level = _lock_level(sku.pk)
    if level.physical + delta < level.reserved:
        raise DomainError("O ajuste deixaria o saldo físico abaixo do reservado.")
    level.physical += delta
    level.save(update_fields=["physical", "updated_at"])
    return StockMovement.objects.create(sku=sku, kind=StockMovement.Kind.ADJUST, quantity=delta, actor=actor, reason=reason)


@transaction.atomic
def return_to_quarantine(sku: SKU, quantity: int, *, key: str, actor=None, reason: str = "Devolução") -> StockMovement:
    if (found := _existing(key)) is not None:
        return found
    level = _lock_level(sku.pk)
    level.quarantine += quantity
    level.save(update_fields=["quarantine", "updated_at"])
    return StockMovement.objects.create(sku=sku, kind=StockMovement.Kind.RETURN_QUARANTINE, quantity=quantity,
                                        idempotency_key=key, actor=actor, reason=reason)


@transaction.atomic
def resolve_quarantine(sku: SKU, quantity: int, *, approved: bool, actor, reason: str) -> StockMovement:
    """LOG-03: devolvido só volta a vendável após inspeção e aprovação."""
    if actor is None or not reason.strip():
        raise DomainError("Inspeção de devolução exige responsável e motivo.")
    level = _lock_level(sku.pk)
    if quantity > level.quarantine:
        raise DomainError("Quantidade maior que o saldo em inspeção.")
    level.quarantine -= quantity
    if approved:
        level.physical += quantity
    else:
        level.damaged += quantity
    level.save()
    kind = StockMovement.Kind.RETURN_APPROVED if approved else StockMovement.Kind.RETURN_REJECTED
    return StockMovement.objects.create(sku=sku, kind=kind, quantity=quantity, actor=actor, reason=reason)
