from datetime import timedelta

from django.utils import timezone

from apps.core.services import get_setting

from .models import Ticket


def open_ticket(user, *, kind: str, subject: str, description: str, reference: str = "", dedupe: str = "") -> Ticket:
    if dedupe:
        found = Ticket.objects.filter(user=user, reference=reference, subject=subject, kind=kind).first()
        if found:
            return found
    return Ticket.objects.create(
        user=user, kind=kind, subject=subject[:160], description=description, reference=reference,
        due_at=timezone.now() + timedelta(hours=int(get_setting("support_sla_hours"))),
    )
