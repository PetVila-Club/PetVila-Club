"""Indicadores (MET-01/02) e exportação aberta da operação (ADM-03)."""

from __future__ import annotations

from datetime import date, timedelta

from django.db.models import Count, Sum
from django.utils import timezone
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .services import Roles, audit, require_role

EXPORT_SCHEMA_VERSION = "1.0"


def compute_metrics(start: date | None = None, end: date | None = None) -> dict:
    from apps.core.models import OperationalAlert
    from apps.curation.models import CycleKit
    from apps.logistics.models import Shipment
    from apps.orders.models import Order
    from apps.payments.models import Payment
    from apps.reviews.models import Review
    from apps.subscriptions.models import Cycle, Subscription

    end = end or timezone.localdate()
    start = start or (end - timedelta(days=30))
    active = Subscription.objects.filter(status=Subscription.Status.ACTIVE)
    mrr = 0
    for sub in active:
        monthly = sub.total_per_cycle_cents if sub.kind == Subscription.Kind.KIT else int(sub.total_per_cycle_cents * 30 / sub.frequency_days)
        mrr += monthly
    paid_orders = Order.objects.filter(paid_at__date__gte=start, paid_at__date__lte=end)
    paid_count = paid_orders.count()
    revenue = paid_orders.aggregate(s=Sum("total_cents"))["s"] or 0
    refunds = Payment.objects.filter(updated_at__date__gte=start, updated_at__date__lte=end).aggregate(s=Sum("refunded_cents"))["s"] or 0
    due = Payment.objects.filter(due_date__gte=start, due_date__lt=min(end, timezone.localdate()))
    due_count = due.count()
    overdue_count = due.exclude(status__in=["CONFIRMED", "RECEIVED", "RECEIVED_IN_CASH", "REFUNDED", "DELETED"]).count()
    started = Subscription.objects.filter(started_at__date__lt=start, status__in=["active", "past_due", "paused", "canceled"]).count()
    canceled = Subscription.objects.filter(cancel_requested_at__date__gte=start, cancel_requested_at__date__lte=end).count()
    paused = Subscription.objects.filter(status=Subscription.Status.PAUSED).count()
    delivered = Shipment.objects.filter(delivered_at__date__gte=start, delivered_at__date__lte=end)
    ratings = Review.objects.filter(created_at__date__gte=start, created_at__date__lte=end)
    avg_rating = None
    if ratings.exists():
        avg_rating = round(sum(r.rating for r in ratings) / ratings.count(), 2)

    return {
        "period": {"start": start.isoformat(), "end": end.isoformat()},
        "active_subscriptions": active.count(),
        "mrr_cents": mrr,
        "paid_orders": paid_count,
        "store_revenue_cents": revenue,
        "refunded_cents": refunds,
        "average_ticket_cents": (revenue // paid_count) if paid_count else None,
        "delinquency_rate": round(overdue_count / due_count, 4) if due_count else None,
        "churn_rate": round(canceled / started, 4) if started else None,
        "paused_subscriptions": paused,
        "deliveries_completed": delivered.count(),
        "average_rating": avg_rating,
        "queues": {
            "cycles_awaiting_curation": Cycle.objects.filter(status=Cycle.Status.PAID, subscription__kind="kit").count(),
            "kits_to_review": CycleKit.objects.filter(status__in=["suggested", "needs_review"]).count(),
            "kits_to_close": CycleKit.objects.filter(status="approved").count(),
            "shipments_open": Shipment.objects.filter(status__in=["pending", "picking", "divergent", "checked"]).count(),
            "open_alerts": OperationalAlert.objects.exclude(status="resolved").count(),
            "alerts_by_kind": dict(
                OperationalAlert.objects.exclude(status="resolved").values_list("kind").annotate(c=Count("id")).values_list("kind", "c")
            ),
        },
        "notes": "Receita da loja = pedidos pagos no período (sem estornos). Margens dependem da política contábil aprovada.",
    }


def build_export() -> dict:
    """Amostra suficiente para reconstruir pedido, cão, assinatura, composição e linhas entregues por ID."""
    from apps.curation.models import CycleKit
    from apps.logistics.models import Shipment
    from apps.orders.models import Order
    from apps.pets.models import Dog
    from apps.subscriptions.models import Subscription

    return {
        "schema_version": EXPORT_SCHEMA_VERSION,
        "generated_at": timezone.now().isoformat(),
        "currency": "BRL",
        "money_unit": "cents",
        "dogs": [
            {"id": d.pk, "tutor_id": d.tutor_id, "name": d.name, "size": d.size, "profile_version": d.profile_version,
             "is_active": d.is_active}
            for d in Dog.objects.all()
        ],
        "subscriptions": [
            {"id": s.pk, "number": s.number, "user_id": s.user_id, "dog_id": s.dog_id, "kind": s.kind, "status": s.status,
             "plan": s.plan.code if s.plan else None, "offer_id": s.offer_id, "sku_id": s.sku_id, "price_cents": s.price_cents,
             "provider_subscription_id": s.asaas_subscription_id,
             "cycles": [{"id": c.pk, "number": c.number, "status": c.status, "provider_payment_id": c.external_payment_id,
                         "price_cents": c.price_cents} for c in s.cycles.all()]}
            for s in Subscription.objects.select_related("plan").prefetch_related("cycles")
        ],
        "kits": [
            {"id": k.pk, "cycle_id": k.cycle_id, "dog_id": k.dog_id, "status": k.status, "composition_id": k.composition_id,
             "profile_version": k.profile_version.version, "snapshot": k.snapshot,
             "lines": [{"id": line.pk, "sku_id": line.sku_id, "sku_code": line.sku.code, "quantity": line.quantity,
                        "status": line.status, "replaces": line.replaces_id} for line in k.lines.select_related("sku")]}
            for k in CycleKit.objects.select_related("profile_version")
        ],
        "orders": [
            {"id": o.pk, "number": o.number, "user_id": o.user_id, "status": o.status, "total_cents": o.total_cents,
             "discount_cents": o.discount_cents, "shipping_cents": o.shipping_cents,
             "lines": [{"id": line.pk, "sku_id": line.sku_id, "sku_code": line.sku_code, "quantity": line.quantity,
                        "unit_price_cents": line.unit_price_cents} for line in o.lines.all()],
             "payments": [{"provider_id": p.external_id, "status": p.status, "value_cents": p.value_cents,
                           "refunded_cents": p.refunded_cents} for p in o.payments.all()]}
            for o in Order.objects.prefetch_related("lines", "payments")
        ],
        "shipments": [
            {"id": s.pk, "number": s.number, "kind": s.kind, "status": s.status, "order_id": s.order_id, "cycle_id": s.cycle_id,
             "resend_of": s.resend_of_id, "tracking_code": s.tracking_code,
             "lines": [{"id": line.pk, "sku_id": line.sku_id, "sku_code": line.sku_code, "quantity": line.quantity,
                        "dog_id": line.dog_id, "lot_id": line.lot_id} for line in s.lines.all()]}
            for s in Shipment.objects.prefetch_related("lines")
        ],
    }


@api_view(["GET"])
def metrics_view(request):
    require_role(request.user, Roles.GESTOR, Roles.FINANCEIRO, Roles.OPERACAO, Roles.CURADOR)
    return Response(compute_metrics())


@api_view(["GET"])
def export_view(request):
    require_role(request.user, Roles.GESTOR, Roles.FINANCEIRO)
    audit(request.user, "data_exported", request.user, changes={"schema_version": EXPORT_SCHEMA_VERSION})
    return Response(build_export())
