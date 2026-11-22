"""MCP server settings: see the openspec mcp-tools spec."""

import pytest

from filaments_mcp.config import DEFAULT_API_URL, ConfigError, load_config


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for key in ("FILAMENTS_API_TOKEN", "FILAMENTS_API_URL"):
        monkeypatch.delenv(key, raising=False)


def test_defaults_to_the_local_api(monkeypatch):
    monkeypatch.setenv("FILAMENTS_API_TOKEN", "t" * 40)

    assert load_config().api_url == DEFAULT_API_URL


def test_trailing_slash_is_dropped(monkeypatch):
    monkeypatch.setenv("FILAMENTS_API_TOKEN", "t" * 40)
    monkeypatch.setenv("FILAMENTS_API_URL", "http://web:8000/api/")

    assert load_config().api_url == "http://web:8000/api"


def test_missing_token_names_the_setting():
    with pytest.raises(ConfigError, match="FILAMENTS_API_TOKEN"):
        load_config()


@pytest.mark.parametrize("url", ["127.0.0.1:8000/api", "ftp://host/api", "web:8000"])
def test_url_without_http_scheme_is_rejected(monkeypatch, url):
    monkeypatch.setenv("FILAMENTS_API_TOKEN", "t" * 40)
    monkeypatch.setenv("FILAMENTS_API_URL", url)

    with pytest.raises(ConfigError, match="FILAMENTS_API_URL"):
        load_config()
