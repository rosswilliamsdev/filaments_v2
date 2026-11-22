"""Settings for the MCP server, read from the environment (see `.env.example`)."""

import os
from dataclasses import dataclass

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
