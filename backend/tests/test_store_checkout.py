"""CHK-01/02/03, LOJ-02 (H09), EST-01 (H06), PAG-02 (H05), PAG-03 (H08 parcial)."""

import uuid

import pytest

from apps.catalog.models import SKU
from apps.core.exceptions import DomainError
from apps.inventory.models import StockLevel
from apps.orders.models import Order
from apps.payments.models import Payment
from apps.payments.services import request_refund
from apps.subscriptions.models import Subscription

from .conftest import webhook


def sku(slug):
    return SKU.objects.get(product__slug=slug)


def quote(client, items, cep="01310100"):
    return client.post("/api/v1/checkout/quote/", {"items": items, "cep": cep}, format="json").json()


def checkout(client, user, items, total, key=None, **extra):
    return client.post(
        "/api/v1/checkout/store/",
        {"items": items, "address_id": user.addresses.first().pk, "billing_type": "PIX", "expected_total_cents": total,
         "accept_terms": True, **extra},
        format="json", HTTP_IDEMPOTENCY_KEY=key or uuid.uuid4().hex,
    )


def test_quote_math_and_cep(auth, tutor):
    client = auth(tutor)
    s = sku("bolinha-vila")
    q = quote(client, [{"sku_id": s.pk, "quantity": 2}])
    assert q["subtotal_cents"] == 2 * 3990
    assert q["shipping_cents"] == 1490
    assert q["total_cents"] == q["subtotal_cents"] - q["discount_cents"] + q["shipping_cents"]
    blocked = quote(client, [{"sku_id": s.pk, "quantity": 1}], cep="69900000")
    assert blocked["can_checkout"] is False
    assert any("CEP" in p for p in blocked["problems"])


def test_member_price_only_for_active_subscriber(auth, tutor):
    client = auth(tutor)
    s = sku("bolinha-vila")
    assert quote(client, [{"sku_id": s.pk, "quantity": 1}])["member_pricing"] is False
    Subscription.objects.create(user=tutor, kind="kit", status="active", price_cents=20990, billing_type="PIX",
                                shipping_address={}, dog=tutor.dogs.first())
    q = quote(client, [{"sku_id": s.pk, "quantity": 1}])
    assert q["member_pricing"] is True
    assert q["lines"][0]["unit_price_cents"] == 3590


def test_browser_cannot_force_discount(auth, tutor):
    client = auth(tutor)
    s = sku("bolinha-vila")
    response = checkout(client, tutor, [{"sku_id": s.pk, "quantity": 1, "unit_price_cents": 1}], 3590 + 1490)
    assert response.status_code == 409
    assert response.json()["code"] == "total_changed"
    assert response.json()["quote"]["total_cents"] == 3990 + 1490


def test_checkout_creates_single_order_and_reserves(auth, tutor):
    client = auth(tutor)
    s = sku("bolinha-vila")
    total = 3990 + 1490
    key = uuid.uuid4().hex
    first = checkout(client, tutor, [{"sku_id": s.pk, "quantity": 1}], total, key=key)
    assert first.status_code == 201, first.json()
    again = checkout(client, tutor, [{"sku_id": s.pk, "quantity": 1}], total, key=key)
    assert again.json()["id"] == first.json()["id"]
    assert Order.objects.filter(user=tutor).count() == 1
    level = StockLevel.objects.get(sku=s)
    assert level.reserved == 1
    body = first.json()
    assert body["payment"]["pix_payload"]
    assert body["status"] == "pending_payment"


def test_last_unit_is_not_sold_twice(auth, tutor, other_tutor):
    s = sku("pelucia-patinha")  # estoque inicial 3
    total = 3 * 4490 + 1490
    a = checkout(auth(tutor), tutor, [{"sku_id": s.pk, "quantity": 3}], total)
    assert a.status_code == 201
    b = checkout(auth(other_tutor), other_tutor, [{"sku_id": s.pk, "quantity": 1}], 4490 + 1490)
    assert b.status_code == 409
    level = StockLevel.objects.get(sku=s)
    assert level.reserved == 3 and level.available == 0


def test_webhook_duplicate_late_and_out_of_order(auth, api, tutor):
    client = auth(tutor)
    s = sku("bolinha-vila")
    order = checkout(client, tutor, [{"sku_id": s.pk, "quantity": 1}], 3990 + 1490).json()
    pid = order["payment"]["external_id"]

    assert webhook(api, "PAYMENT_CONFIRMED", pid, "CONFIRMED", event_id="evt_1").json()["result"] == "paid"
    assert webhook(api, "PAYMENT_CONFIRMED", pid, "CONFIRMED", event_id="evt_1").json()["result"] == "duplicate"
    assert webhook(api, "PAYMENT_RECEIVED", pid, "RECEIVED", event_id="evt_2").json()["result"] == "status:RECEIVED"
    late = webhook(api, "PAYMENT_OVERDUE", pid, "OVERDUE", event_id="evt_0")
    assert late.json()["result"].startswith("ignored:late_event")

    db_order = Order.objects.get(pk=order["id"])
    assert db_order.status == "paid"
    assert db_order.shipments.count() == 1
    assert Payment.objects.get(external_id=pid).status == "RECEIVED"


def test_fake_webhook_is_rejected(api, seeded):
    response = api.post("/api/v1/payments/asaas/webhook/", {"event": "PAYMENT_CONFIRMED", "payment": {"id": "x"}},
                        format="json", HTTP_ASAAS_ACCESS_TOKEN="errado")
    assert response.status_code == 401


def test_value_mismatch_goes_to_reconciliation_queue(auth, api, tutor):
    from apps.core.models import OperationalAlert

    order = checkout(auth(tutor), tutor, [{"sku_id": sku("bolinha-vila").pk, "quantity": 1}], 3990 + 1490).json()
    webhook(api, "PAYMENT_CONFIRMED", order["payment"]["external_id"], "CONFIRMED", value=1.00)
    assert OperationalAlert.objects.filter(kind="reconciliation").exists()


def test_refund_never_exceeds_capture(auth, api, tutor, staff):
    order = checkout(auth(tutor), tutor, [{"sku_id": sku("bolinha-vila").pk, "quantity": 1}], 3990 + 1490).json()
    pid = order["payment"]["external_id"]
    webhook(api, "PAYMENT_CONFIRMED", pid, "CONFIRMED")
    payment = Payment.objects.get(external_id=pid)
    request_refund(payment, 3000, actor=staff["financeiro"], reason="Item avariado", key="r1")
    request_refund(payment, 3000, actor=staff["financeiro"], reason="Item avariado", key="r1")  # repetição
    payment.refresh_from_db()
    assert payment.refunded_cents == 3000
    with pytest.raises(DomainError):
        request_refund(payment, 3000, actor=staff["financeiro"], reason="De novo", key="r2")
    from apps.core.services import PermissionDeniedError

    with pytest.raises(PermissionDeniedError):
        request_refund(payment, 100, actor=staff["atendimento"], reason="Fora da alçada", key="r3")


def test_expired_order_releases_reservation_once(auth, tutor):
    from django.utils import timezone

    from apps.orders.services import expire_unpaid_orders

    s = sku("bolinha-vila")
    order = checkout(auth(tutor), tutor, [{"sku_id": s.pk, "quantity": 2}], 2 * 3990 + 1490).json()
    Order.objects.filter(pk=order["id"]).update(expires_at=timezone.now())
    assert expire_unpaid_orders() == 1
    assert expire_unpaid_orders() == 0
    assert StockLevel.objects.get(sku=s).reserved == 0


def test_product_list_shows_member_price_to_everyone(api, auth, tutor):
    """A vitrine mostra o preço de membro (SKU a SKU) também para quem ainda não assinou."""
    def bolinha(client):
        return next(p for p in client.get("/api/v1/catalog/products/").json() if p["slug"] == "bolinha-vila")

    guest = bolinha(api)
    assert guest["from_price_cents"] == 3990
    assert guest["from_member_price_cents"] == 3590
    assert bolinha(auth(tutor))["from_member_price_cents"] == 3590


def test_store_menu_tree_and_section_filter(api, seeded):
    """Menu da loja: departamentos com subcategorias; filtrar pelo departamento traz as subcategorias."""
    menu = {d["slug"]: [c["slug"] for c in d["children"]] for d in api.get("/api/v1/catalog/departments/").json()}
    assert list(menu)[:4] == ["alimentos", "higiene-e-cuidado", "mordedores", "brinquedos"]
    assert {"snacks", "snacks-naturais", "racao-seca", "racao-umida"} <= set(menu["alimentos"])
    food = api.get("/api/v1/catalog/products/?section=alimentos").json()
    assert {p["store_category"]["parent"]["slug"] for p in food} == {"alimentos"}
    snacks = api.get("/api/v1/catalog/products/?section=snacks").json()
    assert snacks and all(p["store_category"]["slug"] == "snacks" for p in snacks)
