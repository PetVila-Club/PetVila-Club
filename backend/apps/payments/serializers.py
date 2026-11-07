from rest_framework import serializers

from .models import Payment


class PaymentSerializer(serializers.ModelSerializer):
    status_label = serializers.CharField(read_only=True)
    is_paid = serializers.BooleanField(read_only=True)
    reference = serializers.SerializerMethodField()

    class Meta:
        model = Payment
        fields = ["id", "external_id", "purpose", "billing_type", "status", "status_label", "is_paid", "value_cents",
                  "refunded_cents", "due_date", "invoice_url", "bank_slip_url", "pix_payload", "pix_qr_image",
                  "confirmed_at", "reference", "created_at"]

    def get_reference(self, obj) -> str:
        if obj.order_id:
            return obj.order.number
        if obj.cycle_id:
            return obj.cycle.code
        if obj.subscription_id:
            return obj.subscription.number
        return ""
