"""
LOJ-02 / CHK-01: preço e total são sempre calculados no servidor.
Nada enviado pelo navegador (preço, desconto, elegibilidade) é aceito como verdade.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from apps.catalog.models import SKU
from apps.core.exceptions import DomainError
from apps.core.services import get_setting

from .models import ShippingZone


def is_member(user) -> bool:
    """Assinante = possui assinatura de kit ativa e adimplente."""
    if not user or not user.is_authenticated:
        return False
    from apps.subscriptions.models import Subscription

    return Subscription.objects.filter(user=user, kind=Subscription.Kind.KIT, status=Subscription.Status.ACTIVE).exists()


def unit_price(sku: SKU, member: bool) -> int:
    if sku.price_cents is None:
        raise DomainError(f"{sku.display_name} está sem preço e não pode ser vendido.")
    if member and get_setting("subscriber_price_enabled") and sku.member_price_cents:
        return min(sku.member_price_cents, sku.price_cents)
    return sku.price_cents


@dataclass
class QuoteLine:
    sku: SKU
    quantity: int
    list_price_cents: int
    unit_price_cents: int

    @property
    def total_cents(self) -> int:
        return self.unit_price_cents * self.quantity

    @property
    def discount_cents(self) -> int:
        return (self.list_price_cents - self.unit_price_cents) * self.quantity

    def as_dict(self) -> dict:
        return {
            "sku_id": self.sku.pk,
            "sku_code": self.sku.code,
            "name": self.sku.display_name,
            "quantity": self.quantity,
            "list_price_cents": self.list_price_cents,
            "unit_price_cents": self.unit_price_cents,
            "total_cents": self.total_cents,
            "available": self.sku.available_quantity(),
        }


@dataclass
class Quote:
    lines: list[QuoteLine]
    member_pricing: bool
    shipping_cents: int
    eta_days: int | None
    zone: ShippingZone | None
    problems: list[str] = field(default_factory=list)

    @property
    def subtotal_cents(self) -> int:
        return sum(line.list_price_cents * line.quantity for line in self.lines)

    @property
    def discount_cents(self) -> int:
        return sum(line.discount_cents for line in self.lines)

    @property
    def total_cents(self) -> int:
        return self.subtotal_cents - self.discount_cents + self.shipping_cents

    def as_dict(self) -> dict:
        return {
            "lines": [line.as_dict() for line in self.lines],
            "member_pricing": self.member_pricing,
            "subtotal_cents": self.subtotal_cents,
            "discount_cents": self.discount_cents,
            "shipping_cents": self.shipping_cents,
            "total_cents": self.total_cents,
            "eta_days": self.eta_days,
            "zone": self.zone.name if self.zone else None,
            "problems": self.problems,
            "can_checkout": not self.problems,
        }


def build_quote(user, items: list[dict], cep: str | None) -> Quote:
    member = is_member(user)
    problems: list[str] = []
    merged: dict[int, int] = {}
    for item in items:
        try:
            sku_id, qty = int(item["sku_id"]), int(item["quantity"])
        except (KeyError, TypeError, ValueError):
            raise DomainError("Item de carrinho inválido.")
        if qty <= 0 or qty > 50:
            raise DomainError("Quantidade inválida no carrinho.")
        merged[sku_id] = merged.get(sku_id, 0) + qty
    if not merged:
        raise DomainError("Carrinho vazio.")

    skus = {s.pk: s for s in SKU.objects.select_related("product", "stock", "product__category").filter(pk__in=merged)}
    lines: list[QuoteLine] = []
    for sku_id, qty in merged.items():
        sku = skus.get(sku_id)
        if sku is None:
            problems.append(f"Produto {sku_id} não encontrado.")
            continue
        if not sku.is_sellable():
            problems.append(f"{sku.display_name} não está disponível para venda no momento.")
            continue
        if sku.available_quantity() < qty:
            problems.append(f"{sku.display_name}: só {sku.available_quantity()} unidade(s) disponível(is).")
        lines.append(QuoteLine(sku=sku, quantity=qty, list_price_cents=sku.price_cents,
                               unit_price_cents=unit_price(sku, member)))

    zone = None
    shipping = 0
    eta = None
    if cep:
        zone = ShippingZone.for_cep(cep)
        if zone is None:
            problems.append("Ainda não entregamos neste CEP. Estamos ampliando as regiões atendidas.")
        else:
            merchandise = sum(line.total_cents for line in lines)
            shipping = 0 if (zone.free_above_cents and merchandise >= zone.free_above_cents) else zone.price_cents
            eta = zone.eta_days
    return Quote(lines=lines, member_pricing=member, shipping_cents=shipping, eta_days=eta, zone=zone, problems=problems)
