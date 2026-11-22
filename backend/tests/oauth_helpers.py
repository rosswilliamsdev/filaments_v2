"""Helpers for driving Django's OAuth flow in tests, the way Claude does."""

import base64
import hashlib
import re
import secrets
from io import StringIO
from urllib.parse import parse_qs, urlencode, urlparse

from django.contrib.auth import get_user_model
from django.core.management import call_command

from accounts.clients import CLAUDE, CLAUDE_REDIRECT_URI, MCP_INTROSPECTION

__all__ = ["CLAUDE", "CLAUDE_REDIRECT_URI", "MCP_INTROSPECTION"]

PASSWORD = "correct horse battery staple"
RESOURCE = "https://notes.example.com/mcp"


def setup_clients() -> dict[str, tuple[str, str]]:
    """Create the account, run the setup command; return {client name: (client_id, secret)}."""
    get_user_model().objects.create_superuser("ross", password=PASSWORD)
    out = StringIO()
    call_command("setup_oauth_clients", stdout=out)
    found = re.findall(
        r"(\S+): new secret issued.*?Client ID:\s+(\S+).*?Client secret: (\S+)",
        out.getvalue(),
        re.S,
    )
    return {name: (client_id, secret) for name, client_id, secret in found}


def pkce() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
    return verifier, challenge.rstrip(b"=").decode()


def basic(client_id: str, secret: str) -> str:
    return "Basic " + base64.b64encode(f"{client_id}:{secret}".encode()).decode()


def authorize_url(
    client_id: str, challenge: str | None, resource: str = RESOURCE, **overrides
) -> str:
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": CLAUDE_REDIRECT_URI,
        "scope": "notes",
        "state": "xyz",
        "resource": resource,
    }
    if challenge:
        params |= {"code_challenge": challenge, "code_challenge_method": "S256"}
    params.update(overrides)
    return "/o/authorize/?" + urlencode(params)


def sign_in(client) -> None:
    response = client.post("/accounts/login/", {"username": "ross", "password": PASSWORD})
    assert response.status_code == 302


def get_code(client, client_id: str, challenge: str, resource: str = RESOURCE) -> str:
    response = client.get(authorize_url(client_id, challenge, resource))
    assert response.status_code == 302
    location = urlparse(response["Location"])
    assert f"{location.scheme}://{location.netloc}{location.path}" == CLAUDE_REDIRECT_URI
    query = parse_qs(location.query)
    assert query["state"] == ["xyz"]
    return query["code"][0]


def exchange(client, client_id, secret, code, verifier, resource: str = RESOURCE):
    return client.post(
        "/o/token/",
        {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": CLAUDE_REDIRECT_URI,
            "code_verifier": verifier,
            "client_id": client_id,
            "client_secret": secret,
            "resource": resource,
        },
    )


def introspect(client, credentials, token):
    return client.post("/o/introspect/", {"token": token}, HTTP_AUTHORIZATION=credentials)
