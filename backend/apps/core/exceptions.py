from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler

from .services import PermissionDeniedError


class DomainError(Exception):
    """Regra de negócio violada. Vira HTTP 400/409 com mensagem legível."""

    status_code = status.HTTP_400_BAD_REQUEST

    def __init__(self, message: str, *, code: str = "domain_error", data: dict | None = None, status_code: int | None = None):
        super().__init__(message)
        self.message = message
        self.code = code
        self.data = data or {}
        if status_code:
            self.status_code = status_code


class ConflictError(DomainError):
    status_code = status.HTTP_409_CONFLICT


def api_exception_handler(exc, context):
    if isinstance(exc, DomainError):
        return Response({"detail": exc.message, "code": exc.code, **exc.data}, status=exc.status_code)
    if isinstance(exc, PermissionDeniedError):
        return Response({"detail": str(exc), "code": "forbidden"}, status=status.HTTP_403_FORBIDDEN)
    if isinstance(exc, DjangoValidationError):
        messages = exc.messages if hasattr(exc, "messages") else [str(exc)]
        return Response({"detail": " ".join(messages), "code": "invalid"}, status=status.HTTP_400_BAD_REQUEST)
    return exception_handler(exc, context)
