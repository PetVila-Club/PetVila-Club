from django.contrib import admin
from django.utils import timezone

from apps.core.services import audit

from .models import Ticket, TicketMessage


class MessageInline(admin.StackedInline):
    model = TicketMessage
    extra = 1
    fields = ["body", "internal", "author", "created_at"]
    readonly_fields = ["author", "created_at"]

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ["protocol", "kind", "subject", "user", "status", "assigned_to", "due_at", "created_at"]
    list_filter = ["status", "kind"]
    search_fields = ["subject", "description", "user__email", "reference"]
    readonly_fields = ["user", "kind", "subject", "description", "reference", "created_at", "resolved_at"]
    inlines = [MessageInline]

    def has_add_permission(self, request):
        return False

    def save_formset(self, request, form, formset, change):
        instances = formset.save(commit=False)
        for inst in instances:
            if not inst.pk:
                inst.author = request.user
            inst.save()
        formset.save_m2m()

    def save_model(self, request, obj, form, change):
        if obj.status in (Ticket.Status.RESOLVED, Ticket.Status.CLOSED) and obj.resolved_at is None:
            obj.resolved_at = timezone.now()
        super().save_model(request, obj, form, change)
        audit(request.user, "ticket_updated", obj, changes={"status": obj.status})
