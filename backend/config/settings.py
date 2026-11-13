"""
Configuração do backend PetVila Club.

Tudo que muda entre ambientes vem de variáveis de ambiente (veja backend/.env.example).
Valores monetários são sempre centavos inteiros em BRL; datas em UTC no banco e
apresentadas em America/Sao_Paulo.
"""

from datetime import timedelta
from pathlib import Path
import os

import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


def env_bool(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_list(name: str, default: str = "") -> list[str]:
    return [item.strip() for item in env(name, default).split(",") if item.strip()]


DEBUG = env_bool("DJANGO_DEBUG", False)
SECRET_KEY = env("DJANGO_SECRET_KEY")
if not SECRET_KEY:
    if not DEBUG:
        raise RuntimeError("DJANGO_SECRET_KEY é obrigatório fora do modo DEBUG.")
    SECRET_KEY = "dev-only-insecure-key-change-me-please-0123456789"

ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,backend")
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS", "http://localhost:8080,http://localhost:5173")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "corsheaders",
    "apps.core",
    "apps.accounts",
    "apps.catalog",
    "apps.pets",
    "apps.inventory",
    "apps.plans",
    "apps.subscriptions",
    "apps.curation",
    "apps.orders",
    "apps.payments",
    "apps.logistics",
    "apps.fiscal",
    "apps.reviews",
    "apps.support",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

DATABASES = {
    "default": dj_database_url.config(
        default=env("DATABASE_URL", "postgres://petvila:petvila@localhost:5432/petvila"),
        conn_max_age=60,
    )
}

AUTH_USER_MODEL = "accounts.User"
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 8}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "pt-br"
TIME_ZONE = "America/Sao_Paulo"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "/media/"
MEDIA_ROOT = Path(env("DJANGO_MEDIA_ROOT", str(BASE_DIR / "media")))
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"
                    if not DEBUG else "django.contrib.staticfiles.storage.StaticFilesStorage"},
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_PAGINATION_CLASS": None,
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": env("API_THROTTLE_ANON", "120/min"),
        "user": env("API_THROTTLE_USER", "600/min"),
        "auth": env("API_THROTTLE_AUTH", "10/min"),
    },
    "EXCEPTION_HANDLER": "apps.core.exceptions.api_exception_handler",
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=int(env("JWT_ACCESS_MINUTES", "30"))),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=int(env("JWT_REFRESH_DAYS", "14"))),
    "ROTATE_REFRESH_TOKENS": True,
    "UPDATE_LAST_LOGIN": True,
}

CORS_ALLOWED_ORIGINS = env_list("CORS_ALLOWED_ORIGINS", "http://localhost:5173,http://localhost:8080,http://localhost:8081")

# ---------- Asaas ----------
# Sem ASAAS_API_KEY o backend usa um provedor simulado (somente desenvolvimento),
# que permite testar o fluxo completo localmente sem chamar a API real.
ASAAS_API_KEY = env("ASAAS_API_KEY")
ASAAS_ENV = env("ASAAS_ENV", "sandbox")  # sandbox | production
ASAAS_BASE_URL = env(
    "ASAAS_BASE_URL",
    "https://api.asaas.com/v3" if ASAAS_ENV == "production" else "https://api-sandbox.asaas.com/v3",
)
ASAAS_WEBHOOK_TOKEN = env("ASAAS_WEBHOOK_TOKEN")
ASAAS_TIMEOUT_SECONDS = float(env("ASAAS_TIMEOUT_SECONDS", "15"))
PAYMENTS_FAKE_MODE = not ASAAS_API_KEY
if PAYMENTS_FAKE_MODE and not DEBUG and not env_bool("ALLOW_FAKE_PAYMENTS", False):
    raise RuntimeError("ASAAS_API_KEY é obrigatório fora do modo DEBUG.")

FRONTEND_URL = env("FRONTEND_URL", "http://localhost:8080")

# ---------- Segurança em produção ----------
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
if not DEBUG:
    SECURE_HSTS_SECONDS = int(env("DJANGO_HSTS_SECONDS", "0"))
    SECURE_SSL_REDIRECT = env_bool("DJANGO_SSL_REDIRECT", False)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"plain": {"format": "%(asctime)s %(levelname)s %(name)s %(message)s"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "plain"}},
    "root": {"handlers": ["console"], "level": env("LOG_LEVEL", "INFO")},
}
