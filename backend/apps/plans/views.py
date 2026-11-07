from rest_framework import permissions, serializers, viewsets

from .models import Plan


class PlanSerializer(serializers.ModelSerializer):
    offer = serializers.SerializerMethodField()
    composition = serializers.SerializerMethodField()
    available = serializers.SerializerMethodField()

    class Meta:
        model = Plan
        fields = ["id", "code", "name", "tagline", "description", "base_item_count", "highlight", "extras",
                  "offer", "composition", "available"]

    def _offer(self, obj):
        if not hasattr(obj, "_offer_cache"):
            obj._offer_cache = obj.current_offer()
        return obj._offer_cache

    def get_offer(self, obj):
        """Só a oferta publicada (preço aprovado) é exposta. Preço pendente nunca aparece como oficial (COM-01)."""
        offer = self._offer(obj)
        if offer is None:
            return None
        return {
            "id": offer.pk,
            "version": offer.version,
            "price_cents": offer.price_cents,
            "currency": offer.currency,
            "billing_cycle": offer.billing_cycle,
            "shipping_cents": offer.shipping_cents,
            "commitment_options": offer.commitment_options,
            "benefits": offer.benefits,
            "terms": offer.terms,
        }

    def get_composition(self, obj):
        comp = obj.current_composition()
        return comp.snapshot() if comp else None

    def get_available(self, obj) -> bool:
        offer = self._offer(obj)
        return bool(offer and offer.price_cents) and obj.current_composition() is not None


class PlanViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Plan.objects.filter(is_active=True)
    serializer_class = PlanSerializer
    permission_classes = [permissions.AllowAny]
    authentication_classes = []
    lookup_field = "code"
