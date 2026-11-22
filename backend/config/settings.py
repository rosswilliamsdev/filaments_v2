"""Django settings for Filaments v2.

Every environment-specific value comes from environment variables (see
`.env.example`). The same module serves local development and the laptop
deployment.
"""

import os
from pathlib import Path
from urllib.parse import urlsplit
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


def public_url_settings(public_url: str) -> dict:
    """What Django needs to serve `public_url` from behind Cloudflare and the edge proxy."""
    parts = urlsplit(public_url)
    secure = parts.scheme == "https"
    return {
        "host": parts.hostname,
        "origin": f"{parts.scheme}://{parts.netloc}",
        # Cloudflare -> cloudflared -> edge -> web: the last hop is plain http, so trust
        # the forwarded scheme, but only when the site really is served over https.
        "SECURE_PROXY_SSL_HEADER": ("HTTP_X_FORWARDED_PROTO", "https") if secure else None,
        "SESSION_COOKIE_SECURE": secure,
        "CSRF_COOKIE_SECURE": secure,
    }


def env_url(key: str, default: str) -> str:
    """An absolute http(s) URL without a trailing slash."""
    url = (os.environ.get(key, "").strip() or default).rstrip("/")
    if not url.startswith(("http://", "https://")):
        raise ImproperlyConfigured(f"{key} must start with http:// or https://")
    if urlsplit(url).path:
        # The edge, CSRF origins and the OAuth issuer all assume the site root.
        raise ImproperlyConfigured(f"{key} must be a bare origin, without a path")
    return url


SECRET_KEY = env_required("DJANGO_SECRET_KEY")
# Bearer token the MCP server sends to the API (its only caller). See api/auth.py.
FILAMENTS_API_TOKEN = env_token("FILAMENTS_API_TOKEN")
DEBUG = env_bool("DJANGO_DEBUG")
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")
# The Docker service name: the mcp container calls the API and introspection at
# http://web:8000. Only containers on the Compose network can use this name.
if "web" not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append("web")
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.postgres",
    "oauth2_provider",
    "accounts",
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

# --- OAuth (Claude -> MCP server) ---------------------------------------------------
# The public base URL people and Claude reach this server at: the OAuth issuer.
# Local default; the tunnel URL in step 9.
FILAMENTS_PUBLIC_URL = env_url("FILAMENTS_PUBLIC_URL", "http://127.0.0.1:8000")

# Serve the public URL from behind the tunnel and the edge proxy.
_public = public_url_settings(FILAMENTS_PUBLIC_URL)
if _public["host"] not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append(_public["host"])
if _public["origin"] not in CSRF_TRUSTED_ORIGINS:
    CSRF_TRUSTED_ORIGINS.append(_public["origin"])  # the login form is a POST
SECURE_PROXY_SSL_HEADER = _public["SECURE_PROXY_SSL_HEADER"]
SESSION_COOKIE_SECURE = _public["SESSION_COOKIE_SECURE"]
CSRF_COOKIE_SECURE = _public["CSRF_COOKIE_SECURE"]

LOGIN_URL = "/accounts/login/"
# OAuth sign-ins return to Claude via `next`. A direct sign-in lands on a small
# confirmation page, which the edge allows (the admin is never public).
LOGIN_REDIRECT_URL = "/accounts/signed-in/"

OAUTH2_PROVIDER = {
    "SCOPES": {
        "notes": "Read and write your notes",
        "introspection": "Check access tokens (the MCP server)",
    },
    "DEFAULT_SCOPES": ["notes"],
    # Each client gets only its own scope (Claude: notes; the MCP server: introspection).
    "SCOPES_BACKEND_CLASS": "accounts.scopes.PerClientScopes",
    "ACCESS_TOKEN_EXPIRE_SECONDS": 60 * 60,  # 1 hour
    "REFRESH_TOKEN_EXPIRE_SECONDS": 90 * 24 * 60 * 60,  # 90 days, renewed by rotation
    "ROTATE_REFRESH_TOKEN": True,
    "PKCE_REQUIRED": True,
    # Plain http only for local testing.
    "ALLOWED_REDIRECT_URI_SCHEMES": ["https", "http"] if DEBUG else ["https"],
    # Used as the RFC 8414 issuer even though OIDC itself is off.
    "OIDC_ISS_ENDPOINT": FILAMENTS_PUBLIC_URL,
    "OIDC_ENABLED": False,
    "DCR_ENABLED": False,
    "CIMD_ENABLED": False,
    # RFC 9700 (OAuth security best practice), as OAuth 2.1 and the MCP spec expect.
    # DOT defaults these off for compatibility and turns them on in 4.0.
    "COMPLIANT_BCP_RFC9700_IMPLICIT_GRANT": True,  # no implicit grant
    "COMPLIANT_BCP_RFC9700_PASSWORD_GRANT": True,  # no password grant
    "COMPLIANT_BCP_RFC9700_PKCE_METHOD": True,  # S256 only, never "plain"
    "COMPLIANT_BCP_RFC9700_ACCESS_TOKEN_TRANSPORT": True,  # no tokens in URLs
    "COMPLIANT_BCP_RFC9700_AUTHZ_RESPONSE_ISS": True,  # iss on redirects (mix-up defense)
    "COMPLIANT_BCP_RFC9700_TOKEN_STORAGE": True,  # store token hashes, not tokens
}

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
