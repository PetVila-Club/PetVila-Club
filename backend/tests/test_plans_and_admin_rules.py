"""H02, COM-01/02, KIT-01/02/03, ADM-02."""

import pytest

from apps.catalog.models import Category
from apps.core.exceptions import DomainError
from apps.core.services import PermissionDeniedError
from apps.plans import services
from apps.plans.models import CompositionVersion, KitModel, OfferVersion, Plan


def test_essential_without_price_cannot_be_published(staff):
    offer = OfferVersion.objects.get(plan__code="essential", version=1)
    with pytest.raises(DomainError):
        services.approve_offer(offer, staff["gestor"], "tentativa")
    with pytest.raises(DomainError):
        services.publish_offer(offer, staff["gestor"])
    assert Plan.objects.get(code="essential").current_offer() is None


def test_public_plan_api_hides_pending_price(api, seeded):
    data = {p["code"]: p for p in api.get("/api/v1/plans/").json()}
    assert data["essential"]["offer"] is None
    assert data["essential"]["available"] is False
    assert data["care"]["offer"]["price_cents"] == 20990  # publicado só porque o seed usou --demo-approve
    assert data["essential"]["composition"]["total_items"] == 7
    assert data["care"]["composition"]["total_items"] == 10


def test_draft_reference_price_is_not_official(db):
    from django.core.management import call_command

    call_command("seed_demo", verbosity=0)  # sem --demo-approve
    care = Plan.objects.get(code="care")
    assert care.current_offer() is None
    assert care.offers.get(version=1).price_cents == 20990


def test_support_role_cannot_publish_price(staff):
    offer = OfferVersion.objects.create(plan=Plan.objects.get(code="essential"), version=2, price_cents=17990)
    with pytest.raises(PermissionDeniedError):
        services.approve_offer(offer, staff["atendimento"], "não pode")


def test_new_offer_version_does_not_change_contracted_value(staff, tutor):
    care = Plan.objects.get(code="care")
    old = care.current_offer()
    new = OfferVersion.objects.create(plan=care, version=2, price_cents=21990, commitment_options=[3, 6, 12])
    services.approve_offer(new, staff["gestor"], "Reajuste aprovado em reunião")
    services.publish_offer(new, staff["gestor"])
    old.refresh_from_db()
    assert care.current_offer() == new
    assert old.valid_until is not None


def _draft(plan_code, quantities, confirm=False):
    plan = Plan.objects.get(code=plan_code)
    comp = services.clone_composition(plan.current_composition(), None)
    comp.total_change_confirmed = confirm
    comp.save()
    for slug, qty in quantities.items():
        comp.lines.filter(category__slug=slug).update(quantity=qty)
    return comp


def test_invalid_compositions_are_not_approved(staff):
    negative = _draft("essential", {"snack-padrao": -1})
    errors, _ = services.validate_composition(negative)
    assert any("negativa" in e for e in errors)
    with pytest.raises(DomainError):
        services.approve_composition(negative, staff["curador"])

    empty_cat = Category.objects.create(slug="vazia", name="Categoria sem SKU", is_kit_category=True)
    no_candidates = _draft("essential", {"snack-padrao": 2})
    no_candidates.lines.create(category=empty_cat, quantity=1)
    errors, _ = services.validate_composition(no_candidates)
    assert any("candidato" in e for e in errors)


def test_total_change_requires_confirmation_and_preserves_history(staff):
    draft = _draft("essential", {"snack-padrao": 4})
    errors, _ = services.validate_composition(draft)
    assert any("difere da base" in e for e in errors)
    draft.total_change_confirmed = True
    draft.save()
    services.approve_composition(draft, staff["curador"])
    previous = draft.plan.current_composition()
    services.publish_composition(draft, staff["gestor"])
    draft.refresh_from_db()
    assert draft.previous == previous
    assert draft.plan.current_composition() == draft
    assert previous.lines.get(category__slug="snack-padrao").quantity == 3


def test_sixth_kit_model_is_blocked(seeded):
    care = Plan.objects.get(code="care")
    for i in range(3):
        KitModel.objects.create(plan=care, name=f"Extra {i}")
    assert care.kit_models.filter(status="active").count() == 5
    with pytest.raises(DomainError) as exc:
        services.check_kit_model_limit(care)
    assert "Limite de 5" in exc.value.message
    sixth = KitModel(plan=care, name="Sexto")
    from django.core.exceptions import ValidationError

    with pytest.raises(ValidationError):
        sixth.full_clean()


def test_published_composition_is_immutable_in_admin(admin_client, seeded):
    comp = CompositionVersion.objects.filter(status="published").first()
    response = admin_client.get(f"/painel/plans/compositionversion/{comp.pk}/change/")
    assert response.status_code == 200
    assert b'name="_save"' not in response.content
