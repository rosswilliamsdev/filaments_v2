"""Settings for the MCP server, read from the environment (see `.env.example`)."""

import os
from dataclasses import dataclass
from urllib.parse import urlsplit

DEFAULT_API_URL = "http://127.0.0.1:8000/api"


class ConfigError(Exception):
    """A required setting is missing. The message names it, never its value."""


@dataclass(frozen=True)
class Config:
    api_url: str
    api_token: str


def load_config() -> Config:
    token = os.environ.get("FILAMENTS_API_TOKEN", "").strip()
    if not token:
        raise ConfigError("Missing required environment variable: FILAMENTS_API_TOKEN")
    api_url = os.environ.get("FILAMENTS_API_URL", "").strip() or DEFAULT_API_URL
    if not api_url.startswith(("http://", "https://")):
        raise ConfigError("FILAMENTS_API_URL must start with http:// or https://")
    return Config(api_url=api_url.rstrip("/"), api_token=token)


DEFAULT_INTROSPECTION_URL = "http://web:8000/o/introspect/"


@dataclass(frozen=True)
class HttpConfig:
    """Extra settings for `--http`: the public URL and how to check Claude's tokens."""

    public_url: str
    introspection_url: str
    client_id: str
    client_secret: str

    @property
    def resource_url(self) -> str:
        """The MCP endpoint's public URL: what Claude's tokens must be bound to (`aud`)."""
        return f"{self.public_url}/mcp"

    @property
    def public_host(self) -> str:
        return urlsplit(self.public_url).netloc

    @property
    def public_origin(self) -> str:
        parts = urlsplit(self.public_url)
        return f"{parts.scheme}://{parts.netloc}"


def _flag(key: str) -> bool:
    return os.environ.get(key, "").strip().lower() in {"1", "true", "yes", "on"}


def _required(key: str) -> str:
    value = os.environ.get(key, "").strip()
    if not value:
        raise ConfigError(f"Missing required environment variable for --http: {key}")
    return value


def load_http_config() -> HttpConfig:
    public_url = _required("FILAMENTS_PUBLIC_URL").rstrip("/")
    # Claude only connects over HTTPS. Plain http is allowed only by an explicit,
    # deliberately named override, for testing the stack on one machine.
    insecure_ok = _flag("FILAMENTS_ALLOW_INSECURE_PUBLIC_URL")
    if not public_url.startswith("https://") and not (
        insecure_ok and public_url.startswith("http://")
    ):
        raise ConfigError("FILAMENTS_PUBLIC_URL must start with https:// for --http")
    if urlsplit(public_url).path not in ("", "/"):
        # The edge, Django's CSRF origin and the issuer all assume the site root.
        raise ConfigError("FILAMENTS_PUBLIC_URL must be a bare origin, without a path")
    introspection_url = (
        os.environ.get("FILAMENTS_INTROSPECTION_URL", "").strip() or DEFAULT_INTROSPECTION_URL
    )
    if not introspection_url.startswith(("http://", "https://")):
        raise ConfigError("FILAMENTS_INTROSPECTION_URL must start with http:// or https://")
    return HttpConfig(
        public_url=public_url,
        introspection_url=introspection_url,
        client_id=_required("FILAMENTS_INTROSPECTION_CLIENT_ID"),
        client_secret=_required("FILAMENTS_INTROSPECTION_CLIENT_SECRET"),
    )
