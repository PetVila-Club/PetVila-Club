from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.accounts.views import AddressViewSet, LoginView, MeView, RefreshView, RegisterView
from apps.catalog.views import CategoryViewSet, ProductViewSet, TagViewSet
from apps.core.ops import export_view, metrics_view
from apps.logistics.views import DeliveryViewSet
from apps.orders.views import OrderViewSet, checkout, quote
from apps.payments.views import MyPaymentViewSet, asaas_webhook, simulate_payment
from apps.pets.views import DogViewSet
from apps.plans.views import PlanViewSet
from apps.reviews.views import submit_review
from apps.subscriptions.views import SubscriptionViewSet, contract_food_view, contract_kit_view
from apps.support.views import TicketViewSet

router = DefaultRouter()
router.register("catalog/categories", CategoryViewSet, basename="category")
router.register("catalog/tags", TagViewSet, basename="tag")
router.register("catalog/products", ProductViewSet, basename="product")
router.register("plans", PlanViewSet, basename="plan")
router.register("me/addresses", AddressViewSet, basename="address")
router.register("me/dogs", DogViewSet, basename="dog")
router.register("me/orders", OrderViewSet, basename="order")
router.register("me/subscriptions", SubscriptionViewSet, basename="subscription")
router.register("me/deliveries", DeliveryViewSet, basename="delivery")
router.register("me/payments", MyPaymentViewSet, basename="payment")
router.register("me/tickets", TicketViewSet, basename="ticket")

urlpatterns = [
    path("auth/register/", RegisterView.as_view(), name="register"),
    path("auth/login/", LoginView.as_view(), name="login"),
    path("auth/refresh/", RefreshView.as_view(), name="refresh"),
    path("me/", MeView.as_view(), name="me"),
    path("checkout/quote/", quote, name="quote"),
    path("checkout/store/", checkout, name="checkout-store"),
    path("checkout/subscription/", contract_kit_view, name="checkout-subscription"),
    path("checkout/food/", contract_food_view, name="checkout-food"),
    path("me/reviews/", submit_review, name="review"),
    path("payments/asaas/webhook/", asaas_webhook, name="asaas-webhook"),
    path("payments/simulate/", simulate_payment, name="simulate-payment"),
    path("ops/metrics/", metrics_view, name="ops-metrics"),
    path("ops/export/", export_view, name="ops-export"),
    path("", include(router.urls)),
]
