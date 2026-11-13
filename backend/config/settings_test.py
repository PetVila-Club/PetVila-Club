"""Configuração de testes: provedor de pagamento simulado e token de webhook fixo."""

import os

os.environ.setdefault("DJANGO_DEBUG", "1")
os.environ["ASAAS_API_KEY"] = ""
os.environ["ASAAS_WEBHOOK_TOKEN"] = "test-webhook-token"

from .settings import *  # noqa: E402,F401,F403

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
