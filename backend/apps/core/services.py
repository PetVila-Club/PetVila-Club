"""Serviços transversais: auditoria, parâmetros operacionais, papéis e alertas."""

from __future__ import annotations

from typing import Any

from django.db import IntegrityError, transaction

from .models import AuditLog, OperationalAlert, OperationalSetting

# Valores padrão dos parâmetros. Podem ser alterados no painel sem mexer em código.
DEFAULT_SETTINGS: dict[str, tuple[Any, str]] = {
    "kit_models_max_active_per_plan": (5, "KIT-02: limite de modelos ativos por plano"),
    "variety_window_cycles": (3, "CUR-03: ciclos considerados para evitar repetição de SKU (pendente de aprovação)"),
    "cutoff_days_before_billing": (5, "ASS-01: dias antes da cobrança em que o ciclo fecha (pendente de aprovação)"),
    "dog_required_fields": (["name", "size", "weight_kg", "age"], "PET-01: campos obrigatórios para liberar curadoria"),
    "fiscal_required_for_shipping": (True, "FIS-01: exigir documento fiscal autorizado para expedir"),
    "refund_limit_cents_financeiro": (50000, "PAG-03: alçada de estorno do papel financeiro (centavos)"),
    "store_order_expiration_hours": (48, "Horas até cancelar pedido avulso não pago e liberar reserva"),
    "support_sla_hours": (48, "VIL-03: prazo de primeiro retorno do atendimento"),
    "subscriber_price_enabled": (True, "LOJ-02: aplicar preço de assinante para assinatura ativa e adimplente"),
}


def get_setting(key: str, default: Any = None) -> Any:
    try:
        return OperationalSetting.objects.get(key=key).value
    except OperationalSetting.DoesNotExist:
        if key in DEFAULT_SETTINGS:
            return DEFAULT_SETTINGS[key][0]
        return default


def ensure_default_settings() -> None:
    for key, (value, description) in DEFAULT_SETTINGS.items():
        OperationalSetting.objects.get_or_create(key=key, defaults={"value": value, "description": description})


def audit(actor, action: str, obj, reason: str = "", changes: dict | None = None) -> AuditLog:
    if actor is not None and not getattr(actor, "is_authenticated", False):
        actor = None
    return AuditLog.objects.create(
        actor=actor,
        action=action,
        object_type=obj._meta.label if hasattr(obj, "_meta") else type(obj).__name__,
        object_id=str(getattr(obj, "pk", "")),
        object_repr=str(obj)[:255],
        reason=reason or "",
        changes=changes or {},
    )


def raise_alert(kind: str, title: str, *, detail: str = "", obj=None, dedupe_key: str | None = None) -> OperationalAlert:
    data = dict(kind=kind, title=title[:200], detail=detail)
    if obj is not None:
        data["object_type"] = obj._meta.label
        data["object_id"] = str(obj.pk)
    if dedupe_key:
        existing = OperationalAlert.objects.filter(dedupe_key=dedupe_key).first()
        if existing:
            return existing
        try:
            with transaction.atomic():
                return OperationalAlert.objects.create(dedupe_key=dedupe_key, **data)
        except IntegrityError:
            return OperationalAlert.objects.get(dedupe_key=dedupe_key)
    return OperationalAlert.objects.create(**data)


# ---------- Papéis (ADM-02) ----------
class Roles:
    GESTOR = "gestor"
    CURADOR = "curador"
    OPERACAO = "operacao"
    ATENDIMENTO = "atendimento"
    FINANCEIRO = "financeiro"

    ALL = [GESTOR, CURADOR, OPERACAO, ATENDIMENTO, FINANCEIRO]


def has_role(user, *roles: str) -> bool:
    if not user or not user.is_authenticated or not user.is_active:
        return False
    if user.is_superuser:
        return True
    return user.groups.filter(name__in=roles).exists()


class PermissionDeniedError(Exception):
    pass


def require_role(user, *roles: str) -> None:
    if not has_role(user, *roles):
        raise PermissionDeniedError(
            "Seu papel não permite esta ação. Necessário: " + ", ".join(roles)
        )


def format_brl(cents: int | None) -> str:
    if cents is None:
        return "—"
    value = f"{cents / 100:,.2f}"
    return "R$ " + value.replace(",", "X").replace(".", ",").replace("X", ".")
