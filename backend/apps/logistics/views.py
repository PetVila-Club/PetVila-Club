from rest_framework import serializers, viewsets

from .models import Shipment, ShipmentLine


class DeliveryLineSerializer(serializers.ModelSerializer):
    dog_name = serializers.CharField(source="dog.name", default=None, read_only=True)
    review = serializers.SerializerMethodField()
    replaced_sku = serializers.SerializerMethodField()

    class Meta:
        model = ShipmentLine
        fields = ["id", "sku_code", "product_name", "quantity", "dog", "dog_name", "replaced_sku", "review"]

    def get_review(self, obj):
        review = getattr(obj, "review", None)
        if review is None:
            return None
        return {"id": review.pk, "rating": review.rating, "comment": review.comment, "dog_reaction": review.dog_reaction,
                "allow_public": review.allow_public, "updated_at": review.updated_at}

    def get_replaced_sku(self, obj):
        if obj.kit_line_id and obj.kit_line.replaces_id:
            return {"sku_code": obj.kit_line.replaces.sku.code, "product_name": obj.kit_line.replaces.sku.display_name,
                    "justification": obj.kit_line.justification}
        return None


class DeliverySerializer(serializers.ModelSerializer):
    """VIL-02: só o conteúdo realmente expedido aparece como entregue."""

    number = serializers.CharField(read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    kind_label = serializers.CharField(source="get_kind_display", read_only=True)
    reference = serializers.SerializerMethodField()
    content_status = serializers.SerializerMethodField()
    lines = DeliveryLineSerializer(many=True, read_only=True)
    can_review = serializers.SerializerMethodField()

    class Meta:
        model = Shipment
        fields = ["id", "number", "kind", "kind_label", "status", "status_label", "reference", "content_status",
                  "carrier", "tracking_code", "tracking_url", "shipped_at", "delivered_at", "lines", "can_review",
                  "created_at"]

    def get_reference(self, obj):
        if obj.cycle_id:
            return obj.cycle.code
        if obj.order_id:
            return obj.order.number
        return ""

    def get_content_status(self, obj) -> str:
        if obj.status in (Shipment.Status.SHIPPED, Shipment.Status.DELIVERED, Shipment.Status.EXCEPTION):
            return "confirmado"
        return "previsto"

    def get_can_review(self, obj) -> bool:
        return obj.status == Shipment.Status.DELIVERED


class DeliveryViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = DeliverySerializer

    def get_queryset(self):
        return (
            Shipment.objects.filter(user=self.request.user)
            .exclude(status=Shipment.Status.CANCELED)
            .select_related("cycle__subscription", "order")
            .prefetch_related("lines__dog", "lines__review", "lines__kit_line__replaces__sku__product")
            .order_by("-created_at")
        )
