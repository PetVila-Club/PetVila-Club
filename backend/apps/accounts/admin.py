from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import Address, User


class AddressInline(admin.TabularInline):
    model = Address
    extra = 0


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    ordering = ["-date_joined"]
    list_display = ["email", "full_name", "is_staff", "marketing_opt_in", "date_joined"]
    list_filter = ["is_staff", "is_active", "groups", "marketing_opt_in"]
    search_fields = ["email", "full_name", "cpf", "phone"]
    inlines = [AddressInline]
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Dados pessoais", {"fields": ("full_name", "cpf", "phone")}),
        ("Consentimentos", {"fields": ("marketing_opt_in", "marketing_opt_in_updated_at", "terms_version", "terms_accepted_at")}),
        ("Integrações", {"fields": ("asaas_customer_id",)}),
        ("Acesso", {"fields": ("is_active", "is_staff", "is_superuser", "groups")}),
        ("Datas", {"fields": ("last_login", "date_joined")}),
    )
    readonly_fields = ["marketing_opt_in_updated_at", "terms_accepted_at", "last_login", "date_joined"]
    add_fieldsets = (
        (None, {"classes": ("wide",), "fields": ("email", "full_name", "password1", "password2", "is_staff", "groups")}),
    )
    filter_horizontal = ["groups"]
