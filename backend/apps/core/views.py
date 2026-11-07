from django.conf import settings
from django.db import connection
from django.http import JsonResponse


def health(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        db = "ok"
    except Exception:  # pragma: no cover - depende do ambiente
        db = "error"
    return JsonResponse(
        {"status": "ok" if db == "ok" else "degraded", "database": db, "payments_fake_mode": settings.PAYMENTS_FAKE_MODE},
        status=200 if db == "ok" else 503,
    )
