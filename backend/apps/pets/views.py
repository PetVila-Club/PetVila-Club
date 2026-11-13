from django.db import transaction
from rest_framework import serializers, viewsets
from rest_framework.response import Response

from apps.catalog.models import Tag
from apps.catalog.serializers import TagSerializer
from apps.core.services import audit

from .models import Dog


class DogSerializer(serializers.ModelSerializer):
    preferences = serializers.SlugRelatedField(slug_field="code", queryset=Tag.objects.all(), many=True, required=False)
    restrictions = serializers.SlugRelatedField(slug_field="code", queryset=Tag.objects.all(), many=True, required=False)
    preferences_detail = TagSerializer(source="preferences", many=True, read_only=True)
    restrictions_detail = TagSerializer(source="restrictions", many=True, read_only=True)
    missing_fields = serializers.SerializerMethodField()
    age_years = serializers.IntegerField(read_only=True)

    class Meta:
        model = Dog
        fields = [
            "id", "name", "birth_date", "estimated_age_years", "age_years", "size", "weight_kg", "breed",
            "preferences", "restrictions", "preferences_detail", "restrictions_detail", "notes", "is_active",
            "profile_version", "missing_fields", "created_at",
        ]
        read_only_fields = ["id", "profile_version", "created_at"]

    def get_missing_fields(self, obj) -> list[str]:
        return obj.missing_required_fields()

    def validate_weight_kg(self, value):
        if value is not None and (value <= 0 or value > 120):
            raise serializers.ValidationError("Peso fora da faixa aceita (até 120 kg).")
        return value

    def validate_estimated_age_years(self, value):
        if value is not None and value > 30:
            raise serializers.ValidationError("Idade fora da faixa aceita.")
        return value


class DogViewSet(viewsets.ModelViewSet):
    """PET-01 e VIL-01: o tutor só enxerga os próprios cães; ID de outro tutor retorna 404 sem expor dados."""

    serializer_class = DogSerializer
    http_method_names = ["get", "post", "patch", "head", "options", "delete"]

    def get_queryset(self):
        return Dog.objects.filter(tutor=self.request.user).prefetch_related("preferences", "restrictions")

    @transaction.atomic
    def perform_create(self, serializer):
        dog = serializer.save(tutor=self.request.user)
        dog.snapshot_version()

    @transaction.atomic
    def perform_update(self, serializer):
        dog = serializer.save()
        dog.snapshot_version()

    def destroy(self, request, *args, **kwargs):
        """Inativar não apaga obrigações nem entregas anteriores (PET-04)."""
        dog = self.get_object()
        dog.is_active = False
        dog.save(update_fields=["is_active", "updated_at"])
        audit(request.user, "dog_inactivated", dog)
        return Response(status=204)
