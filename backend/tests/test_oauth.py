"""The OAuth authorization server Claude signs in to: see the openspec oauth-server spec."""

import base64
import datetime as dt
import hashlib
import re
import secrets
from io import StringIO
from urllib.parse import parse_qs, urlencode, urlparse

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.utils import timezone
from oauth2_provider.models import get_access_token_model

from accounts.clients import CLAUDE, CLAUDE_REDIRECT_URI, MCP_INTROSPECTION

pytestmark = pytest.mark.django_db

PASSWORD = "correct horse battery staple"
RESOURCE = "https://notes.example.com/mcp"


@pytest.fixture
def clients() -> dict[str, tuple[str, str]]:
    """Run the setup command; return {client name: (client_id, secret)}."""
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


def authorize_url(client_id: str, challenge: str | None, **overrides) -> str:
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": CLAUDE_REDIRECT_URI,
        "scope": "notes",
        "state": "xyz",
        "resource": RESOURCE,
    }
    if challenge:
        params |= {"code_challenge": challenge, "code_challenge_method": "S256"}
    params.update(overrides)
    return "/o/authorize/?" + urlencode(params)


def sign_in(client) -> None:
    response = client.post("/accounts/login/", {"username": "ross", "password": PASSWORD})
    assert response.status_code == 302


def get_code(client, client_id: str, challenge: str) -> str:
    response = client.get(authorize_url(client_id, challenge))
    assert response.status_code == 302
    location = urlparse(response["Location"])
    assert f"{location.scheme}://{location.netloc}{location.path}" == CLAUDE_REDIRECT_URI
    query = parse_qs(location.query)
    assert query["state"] == ["xyz"]
    return query["code"][0]


def exchange(client, client_id, secret, code, verifier):
    return client.post(
        "/o/token/",
        {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": CLAUDE_REDIRECT_URI,
            "code_verifier": verifier,
            "client_id": client_id,
            "client_secret": secret,
            "resource": RESOURCE,
        },
    )


def introspect(client, credentials, token):
    return client.post("/o/introspect/", {"token": token}, HTTP_AUTHORIZATION=credentials)


@pytest.fixture
def tokens(anon_client, clients) -> dict:
    """Claude's full sign-in: login, authorize with PKCE + resource, exchange the code."""
    client_id, secret = clients[CLAUDE]
    verifier, challenge = pkce()
    sign_in(anon_client)
    response = exchange(
        anon_client, client_id, secret, get_code(anon_client, client_id, challenge), verifier
    )
    assert response.status_code == 200, response.content
    return response.json()


# --- Discovery ------------------------------------------------------------------


def test_metadata_document(anon_client, settings):
    data = anon_client.get("/.well-known/oauth-authorization-server").json()

    issuer = settings.FILAMENTS_PUBLIC_URL
    assert data["issuer"] == issuer
    assert data["authorization_endpoint"] == f"{issuer}/o/authorize/"
    assert data["token_endpoint"] == f"{issuer}/o/token/"
    assert data["introspection_endpoint"] == f"{issuer}/o/introspect/"
    assert "S256" in data["code_challenge_methods_supported"]
    assert {"authorization_code", "refresh_token"} <= set(data["grant_types_supported"])
    assert "notes" in data["scopes_supported"]
    assert "registration_endpoint" not in data
    assert {"implicit", "password"}.isdisjoint(data["grant_types_supported"])
    assert data["response_types_supported"] == ["code"]
    assert data["code_challenge_methods_supported"] == ["S256"]
    assert not data.get("client_id_metadata_document_supported")


@pytest.mark.parametrize("path", ["/o/applications/", "/o/device-authorization/", "/o/userinfo/"])
def test_unneeded_endpoints_do_not_exist(client, clients, path):
    sign_in(client)

    assert client.get(path).status_code == 404


# --- The flow -------------------------------------------------------------------


def test_signed_out_user_is_sent_to_login_then_back(anon_client, clients):
    client_id, _ = clients[CLAUDE]
    url = authorize_url(client_id, pkce()[1])

    response = anon_client.get(url)

    assert response.status_code == 302
    assert response["Location"].startswith("/accounts/login/?next=")
    signed_in = anon_client.post(
        response["Location"], {"username": "ross", "password": PASSWORD, "next": url}
    )
    assert signed_in["Location"] == url


def test_claude_receives_tokens(tokens):
    assert tokens["token_type"] == "Bearer"
    assert tokens["expires_in"] == 3600
    assert tokens["scope"] == "notes"
    assert tokens["access_token"] and tokens["refresh_token"]


def test_introspection_reports_scope_and_audience(anon_client, clients, tokens):
    response = introspect(anon_client, basic(*clients[MCP_INTROSPECTION]), tokens["access_token"])

    data = response.json()
    assert response.status_code == 200
    assert data["active"] is True
    assert data["scope"] == "notes"
    assert RESOURCE in data["aud"]
    assert data["client_id"] == clients[CLAUDE][0]


def test_expired_token_is_inactive(anon_client, clients, tokens):
    # Tokens are stored hashed (RFC 9700), so expire the only one there is.
    assert get_access_token_model().objects.count() == 1
    get_access_token_model().objects.update(expires=timezone.now() - dt.timedelta(seconds=1))

    data = introspect(
        anon_client, basic(*clients[MCP_INTROSPECTION]), tokens["access_token"]
    ).json()

    assert data["active"] is False


def test_refresh_rotates(anon_client, clients, tokens):
    client_id, secret = clients[CLAUDE]
    refresh = {"grant_type": "refresh_token", "client_id": client_id, "client_secret": secret}

    first = anon_client.post("/o/token/", refresh | {"refresh_token": tokens["refresh_token"]})
    reused = anon_client.post("/o/token/", refresh | {"refresh_token": tokens["refresh_token"]})

    assert first.status_code == 200
    assert first.json()["refresh_token"] != tokens["refresh_token"]
    assert first.json()["expires_in"] == 3600
    assert reused.status_code == 400


# --- Rejections -----------------------------------------------------------------


def test_plain_pkce_is_refused(client, clients):
    sign_in(client)
    verifier = secrets.token_urlsafe(48)

    response = client.get(
        authorize_url(
            clients[CLAUDE][0], None, code_challenge=verifier, code_challenge_method="plain"
        )
    )

    assert "code=" not in response.get("Location", "")


def test_tokens_are_not_stored_in_plain_text(tokens):
    stored = get_access_token_model().objects.get()

    assert tokens["access_token"] not in (stored.token, str(stored.token_checksum))


def test_missing_pkce_gets_no_code(client, clients):
    sign_in(client)

    response = client.get(authorize_url(clients[CLAUDE][0], challenge=None))

    assert "code=" not in response.get("Location", "")


def test_wrong_redirect_uri_is_not_followed(client, clients):
    sign_in(client)

    response = client.get(
        authorize_url(clients[CLAUDE][0], pkce()[1], redirect_uri="https://evil.example/cb")
    )

    assert response.status_code != 302 or "evil.example" not in response["Location"]


def test_wrong_code_verifier_gets_no_token(client, clients):
    client_id, secret = clients[CLAUDE]
    _, challenge = pkce()
    sign_in(client)

    response = exchange(client, client_id, secret, get_code(client, client_id, challenge), "x" * 50)

    assert response.status_code == 400


def test_claude_cannot_get_the_introspection_scope(client, clients):
    sign_in(client)

    response = client.get(authorize_url(clients[CLAUDE][0], pkce()[1], scope="introspection"))

    assert "code=" not in response.get("Location", "")


@pytest.mark.parametrize("who", ["claude", "nobody"])
def test_introspection_needs_the_mcp_client(anon_client, clients, tokens, who):
    credentials = basic(*clients[CLAUDE]) if who == "claude" else ""

    response = introspect(anon_client, credentials, tokens["access_token"])

    assert response.status_code in (401, 403)


def test_claude_credentials_in_the_body_cannot_introspect(anon_client, clients, tokens):
    client_id, secret = clients[CLAUDE]

    response = anon_client.post(
        "/o/introspect/",
        {"token": tokens["access_token"], "client_id": client_id, "client_secret": secret},
    )

    assert response.status_code in (401, 403)


def test_mcp_credentials_in_the_body_can_introspect(anon_client, clients, tokens):
    client_id, secret = clients[MCP_INTROSPECTION]

    response = anon_client.post(
        "/o/introspect/",
        {"token": tokens["access_token"], "client_id": client_id, "client_secret": secret},
    )

    assert response.json()["active"] is True


def test_rotated_secret_stops_working(anon_client, clients, tokens):
    call_command("setup_oauth_clients", "--rotate", stdout=StringIO())

    response = introspect(anon_client, basic(*clients[MCP_INTROSPECTION]), tokens["access_token"])

    assert response.status_code in (401, 403)


def test_oauth_token_does_not_open_the_api(anon_client, tokens):
    response = anon_client.get(
        "/api/filaments", HTTP_AUTHORIZATION=f"Bearer {tokens['access_token']}"
    )

    assert response.status_code == 401


def test_mixed_header_and_body_credentials_cannot_introspect(anon_client, clients, tokens):
    # Header names the MCP client (wrong secret); body carries Claude's real credentials.
    mcp_id, _ = clients[MCP_INTROSPECTION]
    claude_id, claude_secret = clients[CLAUDE]

    for scheme in ("Basic", "basic"):
        header = basic(mcp_id, "wrong").replace("Basic", scheme)
        response = anon_client.post(
            "/o/introspect/",
            {
                "token": tokens["access_token"],
                "client_id": claude_id,
                "client_secret": claude_secret,
            },
            HTTP_AUTHORIZATION=header,
        )
        assert response.status_code in (401, 403), scheme
