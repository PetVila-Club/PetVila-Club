from django.contrib import admin

from apps.core.admin_utils import ReadOnlyAdminMixin

from .models import Review, ReviewEdit


class EditInline(ReadOnlyAdminMixin, admin.TabularInline):
    model = ReviewEdit
    fields = ["created_at", "data"]
    readonly_fields = fields
    extra = 0


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ["sku", "dog", "user", "rating", "dog_reaction", "allow_public", "is_published", "flagged_for_curation",
                    "updated_at"]
    list_filter = ["rating", "dog_reaction", "allow_public", "is_published", "flagged_for_curation"]
    search_fields = ["sku__code", "user__email", "dog__name", "comment"]
    readonly_fields = ["user", "shipment_line", "sku", "dog", "rating", "comment", "dog_reaction", "allow_public",
                       "flagged_for_curation"]
    inlines = [EditInline]

    def has_add_permission(self, request):
        return False

    def save_model(self, request, obj, form, change):
        if obj.is_published and not obj.allow_public:
            obj.is_published = False  # publicação só com autorização do tutor
        super().save_model(request, obj, form, change)
