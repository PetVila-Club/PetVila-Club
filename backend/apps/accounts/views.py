from django.db import transaction
from rest_framework import generics, permissions, viewsets
from rest_framework.throttling import ScopedRateThrottle
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from apps.core.services import audit

from .models import Address
from .serializers import AddressSerializer, MeSerializer, RegisterSerializer


class AuthThrottleMixin:
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth"


class LoginView(AuthThrottleMixin, TokenObtainPairView):
    pass


class RefreshView(AuthThrottleMixin, TokenRefreshView):
    pass


class RegisterView(AuthThrottleMixin, generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]
    authentication_classes = []


class MeView(generics.RetrieveUpdateAPIView):
    serializer_class = MeSerializer

    def get_object(self):
        return self.request.user

    def perform_update(self, serializer):
        before = {"marketing_opt_in": self.request.user.marketing_opt_in}
        user = serializer.save()
        if before["marketing_opt_in"] != user.marketing_opt_in:
            audit(user, "marketing_preference_changed", user, changes={"marketing_opt_in": user.marketing_opt_in})


class AddressViewSet(viewsets.ModelViewSet):
    serializer_class = AddressSerializer

    def get_queryset(self):
        return Address.objects.filter(user=self.request.user)

    @transaction.atomic
    def perform_create(self, serializer):
        has_any = Address.objects.filter(user=self.request.user).exists()
        is_default = serializer.validated_data.get("is_default") or not has_any
        if is_default:
            Address.objects.filter(user=self.request.user).update(is_default=False)
        serializer.save(user=self.request.user, is_default=is_default)

    @transaction.atomic
    def perform_update(self, serializer):
        if serializer.validated_data.get("is_default"):
            Address.objects.filter(user=self.request.user).exclude(pk=serializer.instance.pk).update(is_default=False)
        serializer.save()
