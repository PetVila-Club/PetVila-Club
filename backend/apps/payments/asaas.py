"""
Cliente da API do Asaas (v3) e um provedor simulado para desenvolvimento local.

Nunca trafegamos dados de cartão: cartão é pago na fatura hospedada pelo Asaas
(invoiceUrl). Guardamos só IDs externos e referências (PAG-01).
"""

from __future__ import annotations

import logging
import uuid
from datetime import date, timedelta
from decimal import Decimal

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


class AsaasError(Exception):
    def __init__(self, message: str, status: int | None = None, payload: dict | None = None):
        super().__init__(message)
        self.status = status
        self.payload = payload or {}


def cents_to_value(cents: int) -> float:
    return float(Decimal(cents) / 100)


def value_to_cents(value) -> int:
    return int((Decimal(str(value)) * 100).quantize(Decimal("1")))


class AsaasClient:
    def __init__(self, api_key: str, base_url: str, timeout: float = 15):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            "access_token": api_key,
            "Content-Type": "application/json",
            "User-Agent": "PetVilaClub/1.0",
        })

    def _request(self, method: str, path: str, **kwargs) -> dict:
        url = f"{self.base_url}{path}"
        try:
            response = self.session.request(method, url, timeout=self.timeout, **kwargs)
        except requests.RequestException as exc:
            raise AsaasError(f"Falha de comunicação com o Asaas: {exc.__class__.__name__}") from exc
        try:
            data = response.json() if response.content else {}
        except ValueError:
            data = {}
        if response.status_code >= 400:
            errors = data.get("errors") or []
            message = "; ".join(e.get("description", "") for e in errors) or f"HTTP {response.status_code}"
            # Nunca logar o corpo inteiro: pode conter dados pessoais.
            logger.warning("Asaas %s %s -> %s", method, path, response.status_code)
            raise AsaasError(message, status=response.status_code, payload=data)
        return data

    # Clientes
    def create_customer(self, *, name: str, cpf_cnpj: str, email: str, phone: str = "", external_reference: str = "") -> dict:
        body = {"name": name, "cpfCnpj": cpf_cnpj, "email": email, "externalReference": external_reference,
                "notificationDisabled": False}
        if phone:
            body["mobilePhone"] = phone
        return self._request("POST", "/customers", json=body)

    # Cobranças avulsas
    def create_payment(self, *, customer: str, billing_type: str, value_cents: int, due_date: date,
                       description: str, external_reference: str) -> dict:
        return self._request("POST", "/payments", json={
            "customer": customer,
            "billingType": billing_type,
            "value": cents_to_value(value_cents),
            "dueDate": due_date.isoformat(),
            "description": description[:500],
            "externalReference": external_reference,
        })

    def get_payment(self, payment_id: str) -> dict:
        return self._request("GET", f"/payments/{payment_id}")

    def get_pix_qr_code(self, payment_id: str) -> dict:
        return self._request("GET", f"/payments/{payment_id}/pixQrCode")

    def refund_payment(self, payment_id: str, value_cents: int, description: str) -> dict:
        return self._request("POST", f"/payments/{payment_id}/refund",
                             json={"value": cents_to_value(value_cents), "description": description[:500]})

    def delete_payment(self, payment_id: str) -> dict:
        return self._request("DELETE", f"/payments/{payment_id}")

    # Assinaturas
    def create_subscription(self, *, customer: str, billing_type: str, value_cents: int, next_due_date: date,
                            cycle: str, description: str, external_reference: str) -> dict:
        return self._request("POST", "/subscriptions", json={
            "customer": customer,
            "billingType": billing_type,
            "value": cents_to_value(value_cents),
            "nextDueDate": next_due_date.isoformat(),
            "cycle": cycle,
            "description": description[:500],
            "externalReference": external_reference,
        })

    def list_subscription_payments(self, subscription_id: str) -> list[dict]:
        return self._request("GET", f"/subscriptions/{subscription_id}/payments").get("data", [])

    def update_subscription(self, subscription_id: str, **fields) -> dict:
        return self._request("POST", f"/subscriptions/{subscription_id}", json=fields)

    def cancel_subscription(self, subscription_id: str) -> dict:
        return self._request("DELETE", f"/subscriptions/{subscription_id}")


class FakeAsaasClient:
    """Provedor simulado: mesmas respostas essenciais, sem rede. Só para desenvolvimento e testes."""

    def __init__(self):
        self.calls: list[tuple[str, dict]] = []

    def _id(self, prefix: str) -> str:
        return f"{prefix}_fake_{uuid.uuid4().hex[:12]}"

    def _payment(self, *, customer, billing_type, value_cents, due_date, description, external_reference, subscription=None):
        pid = self._id("pay")
        return {
            "id": pid,
            "object": "payment",
            "customer": customer,
            "subscription": subscription,
            "billingType": billing_type,
            "value": cents_to_value(value_cents),
            "netValue": cents_to_value(int(value_cents * 0.97)),
            "status": "PENDING",
            "dueDate": due_date.isoformat(),
            "description": description,
            "externalReference": external_reference,
            "invoiceUrl": f"{settings.FRONTEND_URL}/pagamento-simulado/{pid}",
            "bankSlipUrl": None,
        }

    def create_customer(self, **kwargs) -> dict:
        self.calls.append(("create_customer", kwargs))
        return {"id": self._id("cus"), **kwargs}

    def create_payment(self, **kwargs) -> dict:
        self.calls.append(("create_payment", kwargs))
        return self._payment(**kwargs)

    def get_payment(self, payment_id: str) -> dict:
        from .models import Payment

        payment = Payment.objects.filter(external_id=payment_id).first()
        return {"id": payment_id, "status": payment.status if payment else "PENDING"}

    def get_pix_qr_code(self, payment_id: str) -> dict:
        payload = f"00020126580014br.gov.bcb.pix0136petvila-simulado-{payment_id}5204000053039865802BR"
        return {"encodedImage": "", "payload": payload, "expirationDate": (date.today() + timedelta(days=1)).isoformat()}

    def refund_payment(self, payment_id: str, value_cents: int, description: str) -> dict:
        self.calls.append(("refund_payment", {"payment_id": payment_id, "value_cents": value_cents}))
        return {"id": payment_id, "status": "REFUNDED"}

    def delete_payment(self, payment_id: str) -> dict:
        self.calls.append(("delete_payment", {"payment_id": payment_id}))
        return {"deleted": True, "id": payment_id}

    def create_subscription(self, *, customer, billing_type, value_cents, next_due_date, cycle, description, external_reference) -> dict:
        sid = self._id("sub")
        self.calls.append(("create_subscription", {"id": sid, "value_cents": value_cents}))
        first = self._payment(customer=customer, billing_type=billing_type, value_cents=value_cents, due_date=next_due_date,
                              description=description, external_reference=external_reference, subscription=sid)
        self._first_payments = getattr(self, "_first_payments", {})
        self._first_payments[sid] = first
        return {"id": sid, "status": "ACTIVE", "cycle": cycle, "nextDueDate": next_due_date.isoformat(),
                "value": cents_to_value(value_cents)}

    def list_subscription_payments(self, subscription_id: str) -> list[dict]:
        first = getattr(self, "_first_payments", {}).get(subscription_id)
        return [first] if first else []

    def update_subscription(self, subscription_id: str, **fields) -> dict:
        self.calls.append(("update_subscription", {"id": subscription_id, **fields}))
        return {"id": subscription_id, **fields}

    def cancel_subscription(self, subscription_id: str) -> dict:
        self.calls.append(("cancel_subscription", {"id": subscription_id}))
        return {"deleted": True, "id": subscription_id}


_fake_singleton: FakeAsaasClient | None = None


def get_client():
    global _fake_singleton
    if settings.PAYMENTS_FAKE_MODE:
        if _fake_singleton is None:
            _fake_singleton = FakeAsaasClient()
        return _fake_singleton
    return AsaasClient(settings.ASAAS_API_KEY, settings.ASAAS_BASE_URL, settings.ASAAS_TIMEOUT_SECONDS)
