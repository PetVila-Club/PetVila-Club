"""H03, H12, PET-01/04, VIL-01, PRV-01."""

from apps.pets.models import Dog


def test_tutor_only_sees_own_dogs(auth, tutor, other_tutor):
    dog = tutor.dogs.first()
    me = auth(tutor).get("/api/v1/me/dogs/")
    assert me.status_code == 200 and len(me.json()) == 2
    intruder = auth(other_tutor)
    assert intruder.get(f"/api/v1/me/dogs/{dog.pk}/").status_code == 404
    assert intruder.patch(f"/api/v1/me/dogs/{dog.pk}/", {"name": "Hack"}, format="json").status_code == 404
    dog.refresh_from_db()
    assert dog.name == "Paçoca"


def test_anonymous_cannot_access_minha_vila(api, seeded):
    for path in ["/api/v1/me/", "/api/v1/me/dogs/", "/api/v1/me/orders/", "/api/v1/me/deliveries/"]:
        assert api.get(path).status_code == 401


def test_two_dogs_profiles_do_not_contaminate(auth, tutor):
    client = auth(tutor)
    pacoca, thor = tutor.dogs.order_by("name")
    client.patch(f"/api/v1/me/dogs/{pacoca.pk}/", {"restrictions": ["frango", "peixe"]}, format="json")
    thor.refresh_from_db()
    assert sorted(thor.restrictions.values_list("code", flat=True)) == ["latex"]
    pacoca.refresh_from_db()
    assert pacoca.profile_version == 2
    assert pacoca.versions.count() == 2


def test_missing_required_fields_are_reported(auth, tutor):
    response = auth(tutor).post("/api/v1/me/dogs/", {"name": "Filhote"}, format="json")
    assert response.status_code == 201
    assert "porte" in response.json()["missing_fields"]


def test_inactivating_dog_keeps_history(auth, tutor):
    dog = tutor.dogs.first()
    assert auth(tutor).delete(f"/api/v1/me/dogs/{dog.pk}/").status_code == 204
    assert Dog.objects.filter(pk=dog.pk, is_active=False).exists()


def test_marketing_preference_independent_of_service(auth, tutor):
    client = auth(tutor)
    response = client.patch("/api/v1/me/", {"marketing_opt_in": True}, format="json")
    assert response.json()["marketing_opt_in"] is True
    response = client.patch("/api/v1/me/", {"marketing_opt_in": False}, format="json")
    assert response.json()["marketing_opt_in"] is False
    assert response.json()["marketing_opt_in_updated_at"] is not None


def test_register_requires_terms_and_valid_cpf(api, seeded):
    bad = api.post("/api/v1/auth/register/", {"email": "a@b.com", "full_name": "A", "password": "Senha-forte-9",
                                              "accept_terms": False, "cpf": "123"}, format="json")
    assert bad.status_code == 400
    ok = api.post("/api/v1/auth/register/", {"email": "novo@b.com", "full_name": "Nova Pessoa", "password": "Senha-forte-9",
                                             "accept_terms": True, "cpf": "529.982.247-25"}, format="json")
    assert ok.status_code == 201
    login = api.post("/api/v1/auth/login/", {"email": "novo@b.com", "password": "Senha-forte-9"}, format="json")
    assert login.status_code == 200 and "access" in login.json()


def test_support_ticket_protocol(auth, tutor, other_tutor):
    response = auth(tutor).post("/api/v1/me/tickets/", {"kind": "privacy_access", "subject": "Meus dados",
                                                        "description": "Quero uma cópia."}, format="json")
    assert response.status_code == 201
    body = response.json()
    assert body["protocol"].startswith("PV")
    assert body["status"] == "received"
    assert auth(other_tutor).get(f"/api/v1/me/tickets/{body['id']}/").status_code == 404
