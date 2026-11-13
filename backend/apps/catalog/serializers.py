from rest_framework import serializers

from apps.core.services import get_setting
from apps.orders.pricing import unit_price

from .models import SKU, Category, Product, StoreCategory, Tag


class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ["id", "code", "name", "kind"]


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "slug", "name", "description", "is_kit_category"]


class StoreCategoryRefSerializer(serializers.ModelSerializer):
    parent = serializers.SerializerMethodField()

    class Meta:
        model = StoreCategory
        fields = ["slug", "name", "parent"]

    def get_parent(self, obj):
        return {"slug": obj.parent.slug, "name": obj.parent.name} if obj.parent_id else None


class StoreDepartmentSerializer(serializers.ModelSerializer):
    children = serializers.SerializerMethodField()

    class Meta:
        model = StoreCategory
        fields = ["slug", "name", "children"]

    def get_children(self, obj):
        return [{"slug": c.slug, "name": c.name} for c in obj.children.all() if c.is_active]


class SKUSerializer(serializers.ModelSerializer):
    price_cents = serializers.SerializerMethodField()
    list_price_cents = serializers.IntegerField(source="price_cents", read_only=True)
    member_price_cents = serializers.IntegerField(read_only=True)
    available = serializers.SerializerMethodField()
    sellable = serializers.SerializerMethodField()
    contains = TagSerializer(many=True, read_only=True)

    class Meta:
        model = SKU
        fields = [
            "id", "code", "variant_name", "unit_description", "price_cents", "list_price_cents", "member_price_cents",
            "net_weight_g", "weight_g", "available", "sellable", "contains", "suitable_sizes",
        ]

    def get_price_cents(self, obj) -> int | None:
        """Preço exibido ao usuário atual; o servidor recalcula tudo de novo no checkout."""
        if obj.price_cents is None:
            return None
        return unit_price(obj, self.context.get("is_member", False))

    def get_available(self, obj) -> int:
        return max(0, obj.available_quantity())

    def get_sellable(self, obj) -> bool:
        return obj.is_sellable()


class ProductListSerializer(serializers.ModelSerializer):
    category = CategorySerializer(read_only=True)
    store_category = StoreCategoryRefSerializer(read_only=True)
    picture = serializers.CharField(read_only=True)
    from_price_cents = serializers.SerializerMethodField()
    from_list_price_cents = serializers.SerializerMethodField()
    from_member_price_cents = serializers.SerializerMethodField()
    sellable = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = ["id", "slug", "name", "short_description", "category", "store_category", "picture", "is_recurring_food", "is_originals",
                  "from_price_cents", "from_list_price_cents", "from_member_price_cents", "sellable"]

    def _skus(self, obj):
        return [s for s in obj.skus.all() if s.is_active and s.price_cents]

    def get_from_price_cents(self, obj):
        prices = [unit_price(s, self.context.get("is_member", False)) for s in self._skus(obj)]
        return min(prices) if prices else None

    def get_from_list_price_cents(self, obj):
        prices = [s.price_cents for s in self._skus(obj)]
        return min(prices) if prices else None

    def get_from_member_price_cents(self, obj):
        """Menor preço de membro (SKU a SKU), para mostrar o benefício do Club a quem ainda não é membro."""
        if not get_setting("subscriber_price_enabled"):
            return None
        prices = [unit_price(s, True) for s in self._skus(obj) if s.member_price_cents and s.member_price_cents < s.price_cents]
        return min(prices) if prices else None

    def get_sellable(self, obj) -> bool:
        return any(s.is_sellable() for s in obj.skus.all())


class ProductDetailSerializer(ProductListSerializer):
    skus = serializers.SerializerMethodField()

    class Meta(ProductListSerializer.Meta):
        fields = ProductListSerializer.Meta.fields + ["description", "conservation", "skus"]

    def get_skus(self, obj):
        skus = [s for s in obj.skus.all() if s.is_active]
        return SKUSerializer(skus, many=True, context=self.context).data
