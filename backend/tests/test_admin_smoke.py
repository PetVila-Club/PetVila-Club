"""Painel: todas as listas e telas de edição abrem sem erro (ADM-01)."""

from django.contrib import admin


def test_all_admin_changelists_open(admin_client, seeded):
    for model, model_admin in admin.site._registry.items():
        opts = model._meta
        url = f"/painel/{opts.app_label}/{opts.model_name}/"
        response = admin_client.get(url)
        assert response.status_code == 200, url
        obj = model.objects.first()
        if obj is not None:
            change = admin_client.get(f"{url}{obj.pk}/change/")
            assert change.status_code == 200, f"{url}{obj.pk}/change/"


def test_admin_index_shows_routine(admin_client, seeded):
    response = admin_client.get("/painel/")
    assert response.status_code == 200
    assert "Rotina do dia" in response.content.decode()


def test_form_action_intermediate_page(admin_client, seeded):
    from apps.plans.models import OfferVersion

    offer = OfferVersion.objects.get(plan__code="essential")
    response = admin_client.post("/painel/plans/offerversion/", {"action": "approve", "_selected_action": [offer.pk]})
    assert response.status_code == 200
    assert "Justificativa" in response.content.decode()
    response = admin_client.post("/painel/plans/offerversion/", {"action": "approve", "_selected_action": [offer.pk],
                                                                 "apply": "1", "note": "teste"}, follow=True)
    offer.refresh_from_db()
    assert offer.status == "draft"  # sem preço: bloqueado
    assert "sem preço" in response.content.decode()
