"""Shared fixtures for backend tests.

The API requires a bearer token (api/auth.py). Tests use a fixed test token, never the
real `.env` value, and pytest-django's `client` fixture is overridden to send it, so API
tests don't repeat the header. Use `anon_client` to test requests without a token.
"""

import pytest
from django.test import Client

TEST_TOKEN = "test-token-" + "x" * 29  # 40 characters, above the 32 minimum


@pytest.fixture(autouse=True)
def api_token(settings):
    settings.FILAMENTS_API_TOKEN = TEST_TOKEN
    return TEST_TOKEN


@pytest.fixture(autouse=True)
def fast_password_hashing(settings):
    # Production hashing is deliberately slow; sign-in tests make dozens of attempts.
    settings.PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]


@pytest.fixture
def client(api_token):
    """Django test client that authenticates to the API with the test token."""
    return Client(headers={"Authorization": f"Bearer {api_token}"})


@pytest.fixture
def anon_client():
    """Django test client with no Authorization header."""
    return Client()
