import pytest
from django.core.management import call_command
from rest_framework.test import APIClient



@pytest.fixture(autouse=True)
def _settings(settings):
    settings.ASAAS_WEBHOOK_TOKEN = "test-webhook-token"
    settings.PAYMENTS_FAKE_MODE = True
    settings.REST_FRAMEWORK = {**settings.REST_FRAMEWORK, "DEFAULT_THROTTLE_CLASSES": []}


@pytest.fixture
def seeded(db):
    call_command("seed_demo", "--demo-approve", verbosity=0)


@pytest.fixture
def tutor(seeded):
    from apps.accounts.models import User

    return User.objects.get(email="tutor@petvila.local")


@pytest.fixture
def other_tutor(seeded):
    from apps.accounts.models import Address, User

    user = User.objects.create_user("outro@petvila.local", "senha-forte-123", full_name="Outro Tutor", cpf="11144477735")
    Address.objects.create(user=user, recipient="Outro", cep="01001000", street="Praça da Sé", number="1",
                           district="Sé", city="São Paulo", state="SP", is_default=True)
    return user


@pytest.fixture
def staff(seeded):
    from apps.accounts.models import User

    return {role: User.objects.get(email=f"{role}@petvila.local") for role in
            ["gestor", "curador", "operacao", "atendimento", "financeiro"]}


@pytest.fixture
def admin_user(seeded):
    from apps.accounts.models import User

    return User.objects.get(email="admin@petvila.local")


@pytest.fixture
def api():
    return APIClient()


@pytest.fixture
def auth(api):
    def _auth(user):
        client = APIClient()
        client.force_authenticate(user)
        return client

    return _auth


def webhook(client, event, payment_id, status, *, event_id=None, value=None, subscription=None, due_date=None):
    payload = {"event": event, "payment": {"id": payment_id, "status": status}}
    if event_id:
        payload["id"] = event_id
    if value is not None:
        payload["payment"]["value"] = value
    if subscription:
        payload["payment"]["subscription"] = subscription
    if due_date:
        payload["payment"]["dueDate"] = due_date
    return client.post("/api/v1/payments/asaas/webhook/", payload, format="json", HTTP_ASAAS_ACCESS_TOKEN="test-webhook-token")
