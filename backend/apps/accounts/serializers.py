import re

from django.contrib.auth import password_validation
from django.utils import timezone
from rest_framework import serializers

from .models import Address, User

TERMS_VERSION = "2026-11-01"


def only_digits(value: str) -> str:
    return re.sub(r"\D", "", value or "")


def valid_cpf(cpf: str) -> bool:
    cpf = only_digits(cpf)
    if len(cpf) != 11 or cpf == cpf[0] * 11:
        return False
    for i in (9, 10):
        total = sum(int(cpf[n]) * ((i + 1) - n) for n in range(i))
        digit = (total * 10) % 11 % 10
        if digit != int(cpf[i]):
            return False
    return True


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    accept_terms = serializers.BooleanField(write_only=True)

    class Meta:
        model = User
        fields = ["id", "email", "full_name", "cpf", "phone", "password", "marketing_opt_in", "accept_terms"]
        read_only_fields = ["id"]

    def validate_email(self, value):
        value = value.lower().strip()
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("Já existe uma conta com este e-mail.")
        return value

    def validate_cpf(self, value):
        if value and not valid_cpf(value):
            raise serializers.ValidationError("CPF inválido.")
        return only_digits(value)

    def validate_accept_terms(self, value):
        if not value:
            raise serializers.ValidationError("É preciso aceitar os termos de uso e a política de privacidade.")
        return value

    def validate(self, attrs):
        user = User(email=attrs.get("email"), full_name=attrs.get("full_name"))
        password_validation.validate_password(attrs["password"], user)
        return attrs

    def create(self, validated_data):
        validated_data.pop("accept_terms")
        password = validated_data.pop("password")
        marketing = validated_data.pop("marketing_opt_in", False)
        user = User.objects.create_user(
            password=password,
            terms_version=TERMS_VERSION,
            terms_accepted_at=timezone.now(),
            **validated_data,
        )
        user.set_marketing(marketing)
        user.save()
        return user


class MeSerializer(serializers.ModelSerializer):
    is_member = serializers.SerializerMethodField()
    is_staff_panel = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id", "email", "full_name", "cpf", "phone", "marketing_opt_in", "marketing_opt_in_updated_at",
            "terms_version", "terms_accepted_at", "is_member", "is_staff_panel", "date_joined",
        ]
        read_only_fields = ["id", "email", "marketing_opt_in_updated_at", "terms_version", "terms_accepted_at", "date_joined"]

    def get_is_member(self, obj) -> bool:
        from apps.orders.pricing import is_member

        return is_member(obj)

    def get_is_staff_panel(self, obj) -> bool:
        return obj.is_staff

    def validate_cpf(self, value):
        if value and not valid_cpf(value):
            raise serializers.ValidationError("CPF inválido.")
        return only_digits(value)

    def update(self, instance, validated_data):
        if "marketing_opt_in" in validated_data:
            instance.set_marketing(validated_data.pop("marketing_opt_in"))
        return super().update(instance, validated_data)


class AddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = Address
        fields = ["id", "label", "recipient", "cep", "street", "number", "complement", "district", "city", "state", "is_default"]

    def validate_cep(self, value):
        digits = only_digits(value)
        if len(digits) != 8:
            raise serializers.ValidationError("CEP deve ter 8 dígitos.")
        return digits

    def validate_state(self, value):
        return value.upper()
