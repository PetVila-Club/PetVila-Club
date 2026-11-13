from django.db.models import Prefetch, Q
from rest_framework import permissions, viewsets
from rest_framework_simplejwt.authentication import JWTAuthentication

from apps.orders.pricing import is_member

from .models import SKU, Category, Product, StoreCategory, Tag
from .serializers import (CategorySerializer, ProductDetailSerializer, ProductListSerializer, StoreDepartmentSerializer,
                          TagSerializer)


class OptionalJWTAuthentication(JWTAuthentication):
    """Catálogo público: token inválido não bloqueia, só deixa de aplicar preço de assinante."""

    def authenticate(self, request):
        try:
            return super().authenticate(request)
        except Exception:
            return None


class CategoryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Category.objects.filter(show_in_store=True)
    serializer_class = CategorySerializer
    permission_classes = [permissions.AllowAny]
    lookup_field = "slug"


class StoreDepartmentViewSet(viewsets.ReadOnlyModelViewSet):
    """Menu da loja: departamentos com as subcategorias ativas."""

    queryset = StoreCategory.objects.filter(parent__isnull=True, is_active=True).prefetch_related("children")
    serializer_class = StoreDepartmentSerializer
    permission_classes = [permissions.AllowAny]
    lookup_field = "slug"


class TagViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Tag.objects.all()
    serializer_class = TagSerializer
    permission_classes = [permissions.AllowAny]


class ProductViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [permissions.AllowAny]
    authentication_classes = [OptionalJWTAuthentication]
    lookup_field = "slug"

    def get_queryset(self):
        qs = (
            Product.objects.filter(is_active=True, category__show_in_store=True)
            .select_related("category", "store_category__parent")
            .prefetch_related(Prefetch("skus", queryset=SKU.objects.select_related("stock", "product").prefetch_related("contains")))
        )
        category = self.request.query_params.get("category")
        if category:
            qs = qs.filter(category__slug=category)
        section = self.request.query_params.get("section")
        if section:
            qs = qs.filter(Q(store_category__slug=section) | Q(store_category__parent__slug=section))
        if self.request.query_params.get("food") == "1":
            qs = qs.filter(is_recurring_food=True)
        search = self.request.query_params.get("q")
        if search:
            qs = qs.filter(name__icontains=search)
        return qs

    def get_serializer_class(self):
        return ProductDetailSerializer if self.action == "retrieve" else ProductListSerializer

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["is_member"] = is_member(self.request.user)
        return ctx
