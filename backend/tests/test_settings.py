"""Startup checks on secret settings: see the openspec api-auth spec."""

import pytest
from django.core.exceptions import ImproperlyConfigured

from config.settings import env_token

KEY = "FILAMENTS_API_TOKEN"


@pytest.mark.parametrize("value", [None, "", "   ", "changeme", "x" * 31], ids=repr)
def test_missing_or_short_token_fails_startup(monkeypatch, value):
    if value is None:
        monkeypatch.delenv(KEY, raising=False)
    else:
        monkeypatch.setenv(KEY, value)

    with pytest.raises(ImproperlyConfigured, match=KEY) as exc:
        env_token(KEY)

    if value and value.strip():
        assert value not in str(exc.value)


def test_generated_token_passes(monkeypatch):
    token = "a" * 43  # the length of secrets.token_urlsafe(32)
    monkeypatch.setenv(KEY, token)

    assert env_token(KEY) == token
