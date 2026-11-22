"""Django settings for Filaments v2.

Every environment-specific value comes from environment variables (see
`.env.example`). The same module serves local development and the laptop
deployment.
"""

import os
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent


def env_required(key: str) -> str:
    value = os.environ.get(key, "").strip()
    if not value:
        raise ImproperlyConfigured(f"Missing required environment variable: {key}")
    return value


def env_bool(key: str, default: bool = False) -> bool:
    value = os.environ.get(key)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_list(key: str, default: str = "") -> list[str]:
    return [item.strip() for item in os.environ.get(key, default).split(",") if item.strip()]


def env_token(key: str, min_length: int = 32) -> str:
    """A required secret token. Errors name the key but never echo the value."""
    value = env_required(key)
    if len(value) < min_length:
        raise ImproperlyConfigured(f"{key} must be at least {min_length} characters")
    return value


def env_timezone(key: str, default: str = "UTC") -> str:
    """An IANA timezone name, checked at startup so a typo fails loudly."""
    name = os.environ.get(key, "").strip() or default
    try:
        ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        raise ImproperlyConfigured(f"{key} is not a known timezone: {name!r}") from None
    return name


SECRET_KEY = env_required("DJANGO_SECRET_KEY")
# Bearer token the MCP server sends to the API (its only caller). See api/auth.py.
FILAMENTS_API_TOKEN = env_token("FILAMENTS_API_TOKEN")
DEBUG = env_bool("DJANGO_DEBUG")
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.postgres",
    "filaments",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
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

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("POSTGRES_DB", "filaments"),
        "USER": os.environ.get("POSTGRES_USER", "filaments"),
        "PASSWORD": os.environ.get("POSTGRES_PASSWORD", ""),
        "HOST": os.environ.get("POSTGRES_HOST", "localhost"),
        "PORT": os.environ.get("POSTGRES_PORT", "5432"),
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
# Timestamps are stored in UTC (USE_TZ); the home timezone decides what "today" or
# "last Tuesday" means for date filters and how times are shown.
TIME_ZONE = env_timezone("FILAMENTS_TIMEZONE")
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Logging: console always; a file too when DJANGO_LOG_FILE is set (the laptop).
LOG_FILE = os.environ.get("DJANGO_LOG_FILE", "").strip()
_log_handlers = ["console"] + (["file"] if LOG_FILE else [])

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {"format": "{asctime} {levelname} {name}: {message}", "style": "{"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "standard"},
        **(
            {
                "file": {
                    "class": "logging.handlers.RotatingFileHandler",
                    "filename": LOG_FILE,
                    "maxBytes": 5 * 1024 * 1024,
                    "backupCount": 5,
                    "formatter": "standard",
                }
            }
            if LOG_FILE
            else {}
        ),
    },
    "root": {"handlers": _log_handlers, "level": "INFO"},
}
