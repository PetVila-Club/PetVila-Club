from django.contrib import admin

from apps.core.services import audit, format_brl
from apps.inventory.models import StockLevel

from .models import SKU, Category, Product, Tag


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "is_kit_category", "show_in_store", "sort"]
    list_editable = ["sort", "show_in_store"]
    prepopulated_fields = {"slug": ["name"]}


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ["name", "code", "kind"]
    list_filter = ["kind"]
    search_fields = ["name", "code"]


class SKUInline(admin.StackedInline):
    model = SKU
    extra = 0
    fields = [("code", "variant_name", "unit_description"), ("price_cents", "member_price_cents", "cost_cents"),
              ("weight_g", "net_weight_g"), ("length_cm", "width_cm", "height_cm"), "contains", "suitable_sizes",
              ("attributes_complete", "requires_refrigeration", "tracks_lots"), ("ncm", "fiscal_notes"),
              ("is_active", "sellable_in_store")]
    filter_horizontal = ["contains"]


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ["name", "category", "is_active", "is_recurring_food", "is_originals"]
    list_filter = ["category", "is_active", "is_recurring_food", "is_originals"]
    search_fields = ["name", "slug", "skus__code"]
    prepopulated_fields = {"slug": ["name"]}
    inlines = [SKUInline]


@admin.register(SKU)
class SKUAdmin(admin.ModelAdmin):
    list_display = ["code", "product", "variant_name", "price", "member_price", "cost", "available", "attributes_complete",
                    "is_active", "sale_status"]
    list_filter = ["is_active", "attributes_complete", "product__category", "requires_refrigeration", "sellable_in_store"]
    search_fields = ["code", "product__name"]
    filter_horizontal = ["contains"]
    list_select_related = ["product", "stock"]

    @admin.display(description="preço")
    def price(self, obj):
        return format_brl(obj.price_cents)

    @admin.display(description="assinante")
    def member_price(self, obj):
        return format_brl(obj.member_price_cents)

    @admin.display(description="custo")
    def cost(self, obj):
        return format_brl(obj.cost_cents)

    @admin.display(description="disponível")
    def available(self, obj):
        return obj.available_quantity()

    @admin.display(description="venda")
    def sale_status(self, obj):
        missing = obj.missing_sale_data()
        if missing:
            return "Bloqueado: falta " + ", ".join(missing)
        return "Vendável" if obj.is_sellable() else "Sem estoque/inativo"

    def save_model(self, request, obj, form, change):
        before = SKU.objects.filter(pk=obj.pk).values("price_cents", "member_price_cents", "cost_cents").first() if change else None
        super().save_model(request, obj, form, change)
        StockLevel.objects.get_or_create(sku=obj)
        if before:
            after = {"price_cents": obj.price_cents, "member_price_cents": obj.member_price_cents, "cost_cents": obj.cost_cents}
            diff = {k: [before[k], v] for k, v in after.items() if before[k] != v}
            if diff:
                audit(request.user, "sku_price_changed", obj, changes=diff)
