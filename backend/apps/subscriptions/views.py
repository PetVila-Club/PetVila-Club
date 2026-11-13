from rest_framework import serializers, viewsets
from rest_framework.decorators import action, api_view
from rest_framework.response import Response

from apps.orders.views import client_ip
from apps.payments.serializers import PaymentSerializer

from .models import Cycle, Subscription
from .services import (
    cancel_subscription,
    contract_food,
    contract_kits,
    cutoff_for,
    pause_subscription,
    resume_subscription,
)


class CycleSerializer(serializers.ModelSerializer):
    code = serializers.CharField(read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = Cycle
        fields = ["id", "code", "number", "status", "status_label", "billing_date", "cutoff_date", "price_cents",
                  "shipping_cents", "paid_at"]


class SubscriptionSerializer(serializers.ModelSerializer):
    number = serializers.CharField(read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    kind_label = serializers.CharField(source="get_kind_display", read_only=True)
    plan_name = serializers.CharField(source="plan.name", default=None, read_only=True)
    dog_name = serializers.CharField(source="dog.name", default=None, read_only=True)
    sku_name = serializers.SerializerMethodField()
    cycles = CycleSerializer(many=True, read_only=True)
    pending_payment = serializers.SerializerMethodField()
    next_cutoff_date = serializers.SerializerMethodField()
    total_per_cycle_cents = serializers.IntegerField(read_only=True)

    class Meta:
        model = Subscription
        fields = ["id", "number", "kind", "kind_label", "status", "status_label", "plan_name", "dog", "dog_name",
                  "sku_name", "quantity", "frequency_days", "commitment_months", "price_cents", "shipping_cents",
                  "total_per_cycle_cents", "billing_type", "shipping_address", "started_at", "next_billing_date",
                  "next_cutoff_date", "cancel_requested_at", "cancel_effective_date", "cycles", "pending_payment",
                  "created_at"]

    def get_sku_name(self, obj):
        return obj.sku.display_name if obj.sku_id else None

    def get_pending_payment(self, obj):
        payment = obj.payments.filter(status__in=["PENDING", "OVERDUE"]).order_by("-created_at").first()
        return PaymentSerializer(payment).data if payment else None

    def get_next_cutoff_date(self, obj):
        return cutoff_for(obj.next_billing_date) if obj.next_billing_date else None


class SubscriptionViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = SubscriptionSerializer

    def get_queryset(self):
        return (
            Subscription.objects.filter(user=self.request.user)
            .select_related("plan", "dog", "sku__product")
            .prefetch_related("cycles", "payments")
        )

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        sub = self.get_object()
        result = cancel_subscription(sub, actor=request.user, reason=request.data.get("reason", ""))
        sub.refresh_from_db()
        return Response({**result, "subscription": SubscriptionSerializer(sub).data})

    @action(detail=True, methods=["post"])
    def pause(self, request, pk=None):
        sub = self.get_object()
        result = pause_subscription(sub, actor=request.user, reason=request.data.get("reason", ""))
        sub.refresh_from_db()
        return Response({**result, "subscription": SubscriptionSerializer(sub).data})

    @action(detail=True, methods=["post"])
    def resume(self, request, pk=None):
        sub = self.get_object()
        result = resume_subscription(sub, actor=request.user)
        sub.refresh_from_db()
        return Response({**result, "subscription": SubscriptionSerializer(sub).data})


@api_view(["POST"])
def contract_kit_view(request):
    subs = contract_kits(
        request.user,
        plan_code=request.data.get("plan", ""),
        dog_ids=[int(x) for x in request.data.get("dog_ids") or []],
        address_id=request.data.get("address_id"),
        billing_type=request.data.get("billing_type", ""),
        commitment_months=request.data.get("commitment_months"),
        offer_id=int(request.data.get("offer_id") or 0),
        accept_terms=bool(request.data.get("accept_terms")),
        checkout_key=request.headers.get("Idempotency-Key") or request.data.get("idempotency_key", ""),
        ip=client_ip(request),
    )
    return Response({"subscriptions": SubscriptionSerializer(subs, many=True).data}, status=201)


@api_view(["POST"])
def contract_food_view(request):
    sub = contract_food(
        request.user,
        sku_id=int(request.data.get("sku_id") or 0),
        quantity=int(request.data.get("quantity") or 1),
        frequency_days=int(request.data.get("frequency_days") or 30),
        address_id=request.data.get("address_id"),
        billing_type=request.data.get("billing_type", ""),
        dog_id=request.data.get("dog_id"),
        expected_price_cents=int(request.data.get("expected_price_cents") or -1),
        accept_terms=bool(request.data.get("accept_terms")),
        checkout_key=request.headers.get("Idempotency-Key") or request.data.get("idempotency_key", ""),
        ip=client_ip(request),
    )
    return Response({"subscriptions": [SubscriptionSerializer(sub).data]}, status=201)
