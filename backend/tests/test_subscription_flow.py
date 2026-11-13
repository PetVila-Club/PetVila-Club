"""J01/J02/J04/J05/J06 e H01, H04, H05, H07, H10, H11, H13."""

import uuid
from datetime import date, timedelta

import pytest

from apps.catalog.models import SKU
from apps.core.exceptions import DomainError
from apps.core.models import OperationalAlert
from apps.curation import services as curation
from apps.curation.models import CycleKit
from apps.fiscal.models import FiscalDocument
from apps.inventory.models import StockLevel, StockMovement
from apps.logistics import services as logistics
from apps.logistics.models import Shipment
from apps.payments.asaas import get_client
from apps.plans.models import Plan
from apps.subscriptions.models import Cycle, Subscription

from .conftest import webhook


def contract(client, user, dogs, plan="care", key=None, commitment=3):
    plan_obj = Plan.objects.get(code=plan)
    offer = plan_obj.current_offer()
    return client.post(
        "/api/v1/checkout/subscription/",
        {"plan": plan, "dog_ids": [d.pk for d in dogs], "address_id": user.addresses.first().pk, "billing_type": "CREDIT_CARD",
         "commitment_months": commitment, "offer_id": offer.pk if offer else 0, "accept_terms": True},
        format="json", HTTP_IDEMPOTENCY_KEY=key or uuid.uuid4().hex,
    )


def pay_first_cycle(api, sub_payload):
    payment = sub_payload["pending_payment"]
    return webhook(api, "PAYMENT_CONFIRMED", payment["external_id"], "CONFIRMED", event_id=f"evt-{payment['external_id']}",
                   subscription=Subscription.objects.get(pk=sub_payload["id"]).asaas_subscription_id)


def run_until_shipped(kit, staff):
    curation.approve_kit(kit, actor=staff["curador"], note="ok")
    curation.close_kit(kit, actor=staff["operacao"])
    shipment = Shipment.objects.get(cycle=kit.cycle, resend_of=None)
    logistics.start_picking(shipment, actor=staff["operacao"])
    divergences = logistics.check_shipment(shipment, logistics.expected_counts(shipment), actor=staff["operacao"])
    assert divergences == []
    FiscalDocument.objects.filter(shipment=shipment).update(status="authorized", number="123")
    logistics.register_label(shipment, carrier="Transportadora Teste", tracking_code="BR123", actor=staff["operacao"])
    logistics.ship(shipment, actor=staff["operacao"])
    return shipment


def test_essential_with_pending_price_cannot_be_contracted(auth, tutor):
    response = contract(auth(tutor), tutor, [tutor.dogs.first()], plan="essential")
    assert response.status_code == 400
    assert response.json()["code"] == "offer_unavailable"


def test_full_care_cycle_two_dogs(auth, api, tutor, staff):
    client = auth(tutor)
    pacoca, thor = tutor.dogs.order_by("name")
    response = contract(client, tutor, [pacoca, thor])
    assert response.status_code == 201, response.json()
    subs = response.json()["subscriptions"]
    assert len(subs) == 2  # um vínculo por cão (PET-03)
    assert {s["dog_name"] for s in subs} == {"Paçoca", "Thor"}

    for sub in subs:
        assert pay_first_cycle(api, sub).json()["result"] == "paid"
        # Evento repetido com outro ID não gera segundo ciclo (ASS-01)
        payment = sub["pending_payment"]
        webhook(api, "PAYMENT_RECEIVED", payment["external_id"], "RECEIVED", event_id=f"evt2-{payment['external_id']}")
    assert Cycle.objects.filter(subscription__user=tutor).count() == 2
    assert Subscription.objects.filter(user=tutor, status="active").count() == 2

    result = curation.generate_pending_kits()
    assert result["created"] == 2
    kits = {k.dog.name: k for k in CycleKit.objects.all()}

    # H01: Care com 10 unidades
    for kit in kits.values():
        assert sum(line.quantity for line in kit.active_lines) == 10
    # PET-02: Paçoca (restrição frango) não recebe frango; Thor (restrição látex) não recebe látex
    pacoca_skus = {line.sku for line in kits["Paçoca"].active_lines}
    assert not any(s.contains.filter(code="frango").exists() for s in pacoca_skus)
    thor_skus = {line.sku for line in kits["Thor"].active_lines}
    assert not any(s.contains.filter(code="latex").exists() for s in thor_skus)
    # Porte: Paçoca é pequeno, nada exclusivo de médio/grande
    assert all("pequeno" in s.suitable_sizes for s in pacoca_skus)
    # SKU sem cadastro completo nunca é escolhido silenciosamente
    assert SKU.objects.get(product__slug="snack-colorido") not in pacoca_skus | thor_skus
    trace = kits["Paçoca"].trace
    rejected = [r for c in trace["categories"] for r in c["rejected"]]
    assert any("restrição" in r["reason"] for r in rejected)
    assert any(r["kind"] == "unknown" for r in rejected)

    # Kit sem aprovação não gera separação (CUR-02)
    with pytest.raises(DomainError):
        curation.close_kit(kits["Paçoca"], actor=staff["operacao"])

    shipment = run_until_shipped(kits["Paçoca"], staff)
    reserved_before = StockLevel.objects.get(sku=shipment.lines.first().sku).physical
    logistics.ship(shipment, actor=staff["operacao"])  # repetição não baixa de novo
    assert StockLevel.objects.get(sku=shipment.lines.first().sku).physical == reserved_before
    assert StockMovement.objects.filter(kind="ship", reference_id=str(kits["Paçoca"].pk)).count() == shipment.lines.count()

    # Avaliação só depois da entrega confirmada (AVL-01)
    line = shipment.lines.first()
    early = client.post("/api/v1/me/reviews/", {"shipment_line": line.pk, "rating": 5}, format="json")
    assert early.status_code == 403
    logistics.mark_delivered(shipment, actor=staff["operacao"])
    ok = client.post("/api/v1/me/reviews/", {"shipment_line": line.pk, "rating": 5, "dog_reaction": "loved"}, format="json")
    assert ok.status_code == 201
    again = client.post("/api/v1/me/reviews/", {"shipment_line": line.pk, "rating": 4}, format="json")
    assert again.status_code == 200  # edita, não duplica (AVL-02)
    assert line.review.dog == pacoca

    deliveries = client.get("/api/v1/me/deliveries/").json()
    delivered = next(d for d in deliveries if d["id"] == shipment.pk)
    assert delivered["content_status"] == "confirmado"
    assert all(item["dog_name"] == "Paçoca" for item in delivered["lines"])
    pending_thor = next(d for d in deliveries if d["id"] != shipment.pk) if len(deliveries) > 1 else None
    assert pending_thor is None or pending_thor["content_status"] == "previsto"


def test_substitution_on_stockout_and_review_of_delivered_sku(auth, api, tutor, other_tutor, staff):
    client = auth(tutor)
    thor = tutor.dogs.get(name="Thor")
    sub = contract(client, tutor, [thor]).json()["subscriptions"][0]
    pay_first_cycle(api, sub)
    kit = curation.generate_kit(Cycle.objects.get(subscription_id=sub["id"]))
    curation.approve_kit(kit, actor=staff["curador"], note="ok")

    # Ruptura: o brinquedo escolhido acaba antes do fechamento
    toy_line = kit.active_lines.get(category__slug="brinquedo")
    level = StockLevel.objects.get(sku=toy_line.sku)
    level.physical = level.reserved
    level.save()
    with pytest.raises(DomainError) as exc:
        curation.close_kit(kit, actor=staff["operacao"])
    assert exc.value.code == "stockout"
    assert OperationalAlert.objects.filter(kind="stockout").exists()

    # Troca incompatível é bloqueada (mordedor de látex para o Thor)
    latex = SKU.objects.get(product__slug="mordedor-latex")
    with pytest.raises(DomainError):
        curation.substitute_line(toy_line, latex, actor=staff["curador"], justification="ruptura")
    replacement = SKU.objects.get(product__slug="corda-algodao") if toy_line.sku.product.slug != "corda-algodao" \
        else SKU.objects.get(product__slug="bolinha-vila")
    new_line = curation.substitute_line(toy_line, replacement, actor=staff["curador"], justification="Ruptura do original")
    kit.refresh_from_db()
    shipment = run_until_shipped_after_approval(kit, staff)
    logistics.mark_delivered(shipment, actor=staff["operacao"])

    lines = {item.sku_id: item for item in shipment.lines.all()}
    assert replacement.pk in lines and toy_line.sku_id not in lines
    delivery = client.get(f"/api/v1/me/deliveries/{shipment.pk}/").json()
    toy = next(item for item in delivery["lines"] if item["sku_code"] == replacement.code)
    assert toy["replaced_sku"]["sku_code"] == toy_line.sku.code
    # Outro tutor não avalia item deste tutor
    other = auth(other_tutor).post("/api/v1/me/reviews/", {"shipment_line": lines[replacement.pk].pk, "rating": 1}, format="json")
    assert other.status_code == 403
    assert new_line.replaces == toy_line


def run_until_shipped_after_approval(kit, staff):
    curation.close_kit(kit, actor=staff["operacao"])
    shipment = Shipment.objects.get(cycle=kit.cycle, resend_of=None)
    logistics.check_shipment(shipment, logistics.expected_counts(shipment), actor=staff["operacao"])
    FiscalDocument.objects.filter(shipment=shipment).update(status="authorized")
    logistics.register_label(shipment, carrier="Teste", tracking_code="BR999", actor=staff["operacao"])
    return logistics.ship(shipment, actor=staff["operacao"])


def test_fiscal_rejection_and_divergence_block_shipping(auth, api, tutor, staff):
    client = auth(tutor)
    sub = contract(client, tutor, [tutor.dogs.get(name="Thor")]).json()["subscriptions"][0]
    pay_first_cycle(api, sub)
    kit = curation.generate_kit(Cycle.objects.get(subscription_id=sub["id"]))
    curation.approve_kit(kit, actor=staff["curador"], note="ok")
    curation.close_kit(kit, actor=staff["operacao"])
    shipment = Shipment.objects.get(cycle=kit.cycle)
    counts = logistics.expected_counts(shipment)
    first = next(iter(counts))
    counts[first] -= 1
    counts["PV-999"] = 1
    divergences = logistics.check_shipment(shipment, counts, actor=staff["operacao"])
    assert {d["kind"] for d in divergences} == {"falta", "sku_diferente"}
    with pytest.raises(DomainError):
        logistics.ship(shipment, actor=staff["operacao"])
    logistics.check_shipment(shipment, logistics.expected_counts(shipment), actor=staff["operacao"])
    logistics.register_label(shipment, carrier="Teste", tracking_code="BR1", actor=staff["operacao"])
    FiscalDocument.objects.filter(shipment=shipment).update(status="rejected", rejection_reason="NCM")
    with pytest.raises(DomainError) as exc:
        logistics.ship(shipment, actor=staff["operacao"])
    assert exc.value.code == "fiscal_blocked"
    # Etiqueta não é contratada duas vezes
    with pytest.raises(DomainError):
        logistics.register_label(shipment, carrier="Outra", tracking_code="BR2", actor=staff["operacao"])


def test_profile_and_composition_change_after_close_keep_history(auth, api, tutor, staff):
    client = auth(tutor)
    thor = tutor.dogs.get(name="Thor")
    sub = contract(client, tutor, [thor]).json()["subscriptions"][0]
    pay_first_cycle(api, sub)
    kit = curation.generate_kit(Cycle.objects.get(subscription_id=sub["id"]))
    curation.approve_kit(kit, actor=staff["curador"], note="ok")
    curation.close_kit(kit, actor=staff["operacao"])
    kit.refresh_from_db()
    frozen = kit.snapshot

    client.patch(f"/api/v1/me/dogs/{thor.pk}/", {"restrictions": ["latex", "carne-bovina"]}, format="json")
    assert OperationalAlert.objects.filter(kind="profile_changed").exists()

    from apps.plans import services as plan_services

    care = Plan.objects.get(code="care")
    draft = plan_services.clone_composition(care.current_composition(), staff["gestor"])
    draft.lines.filter(category__slug="snack-padrao").update(quantity=3)
    draft.lines.filter(category__slug="snack-natural").update(quantity=1)
    plan_services.approve_composition(draft, staff["curador"])
    plan_services.publish_composition(draft, staff["gestor"])

    kit.refresh_from_db()
    assert kit.snapshot == frozen
    assert kit.profile_version.data["restrictions"] == ["latex"]
    assert kit.composition != care.current_composition()


def test_payment_failure_blocks_release_and_recovery_releases_once(auth, api, tutor):
    client = auth(tutor)
    sub = contract(client, tutor, [tutor.dogs.get(name="Thor")]).json()["subscriptions"][0]
    pid = sub["pending_payment"]["external_id"]
    webhook(api, "PAYMENT_OVERDUE", pid, "OVERDUE", event_id="o1")
    cycle = Cycle.objects.get(subscription_id=sub["id"])
    assert cycle.status == "payment_failed"
    with pytest.raises(DomainError):
        curation.generate_kit(cycle)
    webhook(api, "PAYMENT_CONFIRMED", pid, "CONFIRMED", event_id="o2")
    webhook(api, "PAYMENT_CONFIRMED", pid, "CONFIRMED", event_id="o3")
    cycle.refresh_from_db()
    assert cycle.status == "paid"
    assert Cycle.objects.filter(subscription_id=sub["id"]).count() == 1


def test_cancel_before_and_after_cutoff(auth, api, tutor):
    client = auth(tutor)
    pacoca, thor = tutor.dogs.order_by("name")
    subs = contract(client, tutor, [pacoca, thor]).json()["subscriptions"]
    for sub in subs:
        pay_first_cycle(api, sub)
    before, after = (Subscription.objects.get(pk=s["id"]) for s in subs)

    before.next_billing_date = date.today() + timedelta(days=20)
    before.save()
    response = client.post(f"/api/v1/me/subscriptions/{before.pk}/cancel/", {"reason": "teste"}, format="json").json()
    before.refresh_from_db()
    assert before.status == "canceled"
    assert before.cancel_effective_date == date.today()
    assert ("cancel_subscription", {"id": before.asaas_subscription_id}) in get_client().calls

    after.next_billing_date = date.today() + timedelta(days=2)
    after.save()
    response = client.post(f"/api/v1/me/subscriptions/{after.pk}/cancel/", {}, format="json").json()
    after.refresh_from_db()
    assert after.status == "active"
    assert after.cancel_effective_date == after.next_billing_date
    assert "data de corte" in response["message"]
    assert any(c[0] == "update_subscription" and c[1].get("endDate") for c in get_client().calls)


def test_food_subscription_is_independent_from_kit(auth, api, tutor):
    client = auth(tutor)
    thor = tutor.dogs.get(name="Thor")
    kit_sub = contract(client, tutor, [thor]).json()["subscriptions"][0]
    pay_first_cycle(api, kit_sub)
    food_sku = SKU.objects.get(product__slug="racao-adulto-cordeiro")
    # Assinante ativo paga preço de membro também na recorrência de ração
    response = client.post("/api/v1/checkout/food/", {
        "sku_id": food_sku.pk, "quantity": 1, "frequency_days": 30, "address_id": tutor.addresses.first().pk,
        "billing_type": "CREDIT_CARD", "dog_id": thor.pk, "expected_price_cents": food_sku.member_price_cents, "accept_terms": True,
    }, format="json", HTTP_IDEMPOTENCY_KEY=uuid.uuid4().hex)
    assert response.status_code == 201, response.json()
    food = response.json()["subscriptions"][0]
    pay_first_cycle(api, food)
    food_cycle = Cycle.objects.get(subscription_id=food["id"])
    assert food_cycle.status == "reserved"
    assert Shipment.objects.filter(cycle=food_cycle, kind="food").exists()

    client.post(f"/api/v1/me/subscriptions/{food['id']}/pause/", {}, format="json")
    assert Subscription.objects.get(pk=food["id"]).status == "paused"
    assert Subscription.objects.get(pk=kit_sub["id"]).status == "active"


def test_food_stockout_never_swaps_brand(auth, api, tutor):
    client = auth(tutor)
    food_sku = SKU.objects.get(product__slug="racao-adulto-frango")
    level = StockLevel.objects.get(sku=food_sku)
    level.physical = level.reserved
    level.save()
    response = client.post("/api/v1/checkout/food/", {
        "sku_id": food_sku.pk, "quantity": 1, "frequency_days": 30, "address_id": tutor.addresses.first().pk,
        "billing_type": "CREDIT_CARD", "expected_price_cents": food_sku.price_cents, "accept_terms": True,
    }, format="json", HTTP_IDEMPOTENCY_KEY=uuid.uuid4().hex)
    food = response.json()["subscriptions"][0]
    pay_first_cycle(api, food)
    cycle = Cycle.objects.get(subscription_id=food["id"])
    assert cycle.status == "paid"
    assert not Shipment.objects.filter(cycle=cycle).exists()
    assert OperationalAlert.objects.filter(kind="stockout", title__icontains="ração").exists()


def test_contract_is_idempotent(auth, tutor):
    client = auth(tutor)
    key = uuid.uuid4().hex
    first = contract(client, tutor, [tutor.dogs.get(name="Thor")], key=key)
    second = contract(client, tutor, [tutor.dogs.get(name="Thor")], key=key)
    assert first.status_code == 201 and second.status_code == 201
    assert Subscription.objects.filter(user=tutor).count() == 1
    third = contract(client, tutor, [tutor.dogs.get(name="Thor")])
    assert third.json()["code"] == "dog_already_subscribed"


def test_metrics_and_export_restricted(auth, tutor, staff):
    assert auth(tutor).get("/api/v1/ops/export/").status_code == 403
    assert auth(staff["atendimento"]).get("/api/v1/ops/export/").status_code == 403
    export = auth(staff["gestor"]).get("/api/v1/ops/export/")
    assert export.status_code == 200
    assert export.json()["schema_version"] == "1.0"
    assert auth(staff["gestor"]).get("/api/v1/ops/metrics/").status_code == 200


def test_plan_checkout_with_food_cross_sell_at_member_price(auth, tutor):
    client = auth(tutor)
    thor = tutor.dogs.get(name="Thor")
    food_sku = SKU.objects.get(product__slug="racao-adulto-frango")
    plan = Plan.objects.get(code="care")
    key = uuid.uuid4().hex
    payload = {"plan": "care", "dog_ids": [thor.pk], "address_id": tutor.addresses.first().pk, "billing_type": "CREDIT_CARD",
               "commitment_months": 3, "offer_id": plan.current_offer().pk, "accept_terms": True,
               "food": {"sku_id": food_sku.pk, "quantity": 2, "expected_price_cents": 2 * food_sku.member_price_cents}}
    response = client.post("/api/v1/checkout/subscription/", payload, format="json", HTTP_IDEMPOTENCY_KEY=key)
    assert response.status_code == 201, response.json()
    kinds = sorted(s["kind"] for s in response.json()["subscriptions"])
    assert kinds == ["food", "kit"]
    food = Subscription.objects.get(user=tutor, kind="food")
    assert food.price_cents == 2 * food_sku.member_price_cents
    assert food.checkout_key == f"{key}:racao"
    assert food.dog == thor
    # Retomada idempotente devolve kit e ração, sem duplicar
    again = client.post("/api/v1/checkout/subscription/", payload, format="json", HTTP_IDEMPOTENCY_KEY=key)
    assert len(again.json()["subscriptions"]) == 2
    assert Subscription.objects.filter(user=tutor, kind="food").count() == 1


def test_food_cross_sell_price_is_checked_before_creating_kit(auth, tutor):
    client = auth(tutor)
    thor = tutor.dogs.get(name="Thor")
    food_sku = SKU.objects.get(product__slug="racao-adulto-frango")
    plan = Plan.objects.get(code="care")
    response = client.post("/api/v1/checkout/subscription/", {
        "plan": "care", "dog_ids": [thor.pk], "address_id": tutor.addresses.first().pk, "billing_type": "CREDIT_CARD",
        "commitment_months": 3, "offer_id": plan.current_offer().pk, "accept_terms": True,
        "food": {"sku_id": food_sku.pk, "quantity": 1, "expected_price_cents": food_sku.price_cents},
    }, format="json", HTTP_IDEMPOTENCY_KEY=uuid.uuid4().hex)
    assert response.status_code == 409
    assert response.json()["code"] == "total_changed"
    assert not Subscription.objects.filter(user=tutor).exists()


@pytest.mark.parametrize("billing", ["PIX", "BOLETO"])
def test_recurring_only_accepts_credit_card(auth, tutor, billing):
    client = auth(tutor)
    thor = tutor.dogs.get(name="Thor")
    plan = Plan.objects.get(code="care")
    response = client.post("/api/v1/checkout/subscription/", {
        "plan": "care", "dog_ids": [thor.pk], "address_id": tutor.addresses.first().pk, "billing_type": billing,
        "commitment_months": 3, "offer_id": plan.current_offer().pk, "accept_terms": True,
    }, format="json", HTTP_IDEMPOTENCY_KEY=uuid.uuid4().hex)
    assert response.status_code == 400
    assert response.json()["code"] == "billing_not_allowed"
    food_sku = SKU.objects.get(product__slug="racao-adulto-frango")
    response = client.post("/api/v1/checkout/food/", {
        "sku_id": food_sku.pk, "quantity": 1, "frequency_days": 30, "address_id": tutor.addresses.first().pk,
        "billing_type": billing, "expected_price_cents": food_sku.price_cents, "accept_terms": True,
    }, format="json", HTTP_IDEMPOTENCY_KEY=uuid.uuid4().hex)
    assert response.status_code == 400
    assert response.json()["code"] == "billing_not_allowed"
    assert not Subscription.objects.filter(user=tutor).exists()
