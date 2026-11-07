from django.contrib import admin

from apps.core.admin_utils import ReadOnlyAdminMixin

from .models import Dog, DogProfileVersion


class VersionInline(ReadOnlyAdminMixin, admin.TabularInline):
    model = DogProfileVersion
    fields = ["version", "created_at", "data"]
    readonly_fields = fields
    extra = 0


@admin.register(Dog)
class DogAdmin(admin.ModelAdmin):
    list_display = ["name", "tutor", "size", "weight_kg", "profile_version", "is_active", "missing"]
    list_filter = ["size", "is_active", "restrictions"]
    search_fields = ["name", "tutor__email", "tutor__full_name"]
    filter_horizontal = ["preferences", "restrictions"]
    readonly_fields = ["profile_version"]
    inlines = [VersionInline]

    @admin.display(description="pendências")
    def missing(self, obj):
        return ", ".join(obj.missing_required_fields()) or "—"

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        form.instance.snapshot_version()
