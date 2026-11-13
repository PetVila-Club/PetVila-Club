from rest_framework import permissions, serializers, viewsets
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.response import Response

from apps.catalog.views import OptionalJWTAuthentication
from apps.payments.serializers import PaymentSerializer

from .models import Order, OrderLine
from .pricing import build_quote
from .services import checkout_store


def client_ip(request) -> str:
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    return forwarded.split(",")[0].strip() if forwarded else request.META.get("REMOTE_ADDR", "")


class OrderLineSerializer(serializers.ModelSerializer):
    total_cents = serializers.IntegerField(read_only=True)

    class Meta:
        model = OrderLine
        fields = ["id", "sku_code", "product_name", "variant_name", "quantity", "list_price_cents", "unit_price_cents",
                  "total_cents"]


class OrderSerializer(serializers.ModelSerializer):
    number = serializers.CharField(read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    lines = OrderLineSerializer(many=True, read_only=True)
    payment = serializers.SerializerMethodField()
    shipments = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = ["id", "number", "status", "status_label", "subtotal_cents", "discount_cents", "shipping_cents",
                  "total_cents", "member_pricing", "shipping_address", "eta_days", "billing_type", "lines", "payment",
                  "shipments", "created_at", "paid_at"]

    def get_payment(self, obj):
        payment = obj.payments.order_by("-created_at").first()
        return PaymentSerializer(payment).data if payment else None

    def get_shipments(self, obj):
        return [{"id": s.pk, "number": s.number, "status": s.status, "status_label": s.get_status_display(),
                 "tracking_code": s.tracking_code, "tracking_url": s.tracking_url} for s in obj.shipments.all()]


@api_view(["POST"])
@authentication_classes([OptionalJWTAuthentication])
@permission_classes([permissions.AllowAny])
def quote(request):
    """CHK-01: total calculado no servidor para exibir antes da confirmação."""
    result = build_quote(request.user, request.data.get("items") or [], request.data.get("cep"),
                         subscription_key=request.data.get("subscription_key"))
    return Response(result.as_dict())


@api_view(["POST"])
def checkout(request):
    order = checkout_store(
        request.user,
        items=request.data.get("items") or [],
        address_id=request.data.get("address_id"),
        billing_type=request.data.get("billing_type", ""),
        expected_total_cents=int(request.data.get("expected_total_cents") or -1),
        accept_terms=bool(request.data.get("accept_terms")),
        idempotency_key=request.headers.get("Idempotency-Key") or request.data.get("idempotency_key", ""),
        ip=client_ip(request),
        subscription_key=request.data.get("subscription_key") or "",
    )
    return Response(OrderSerializer(order).data, status=201)


class OrderViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = OrderSerializer

    def get_queryset(self):
        return Order.objects.filter(user=self.request.user).prefetch_related("lines", "payments", "shipments")
