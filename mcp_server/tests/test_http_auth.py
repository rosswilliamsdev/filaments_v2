"""`--http` mode: OAuth on every request. See the openspec mcp-tools spec.

The HTTP app runs in-process; Django's introspection endpoint and the API are faked.
"""

import base64
from urllib.parse import parse_qs

import httpx
import httpx2
import pytest
from conftest import NOTE, TOKEN
from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport

from filaments_mcp.config import Config, ConfigError, HttpConfig, load_http_config
from filaments_mcp.server import allowed_hosts, create_server, http_options, oauth_provider

pytestmark = pytest.mark.anyio

PUBLIC = "https://myfilaments.dev"
RESOURCE = f"{PUBLIC}/mcp"
HTTP = HttpConfig(PUBLIC, "http://web:8000/o/introspect/", "mcp-client", "mcp-secret")
FAR_FUTURE = 4102444800  # 2100-01-01


class FakeIntrospection:
    """Django's /o/introspect/: answers per token, records each call."""

    def __init__(self):
        self.tokens: dict[str, dict] = {
            "good": {"active": True, "scope": "notes", "aud": [RESOURCE]},
            "wrong-scope": {"active": True, "scope": "introspection", "aud": [RESOURCE]},
            "wrong-audience": {
                "active": True,
                "scope": "notes",
                "aud": ["https://other.example/mcp"],
            },
            "inactive": {"active": False},
        }
        self.calls: list[httpx.Request] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.calls.append(request)
        token = parse_qs(request.content.decode())["token"][0]
        claims = self.tokens.get(token, {"active": False})
        if claims.get("active"):
            claims = {"client_id": "claude", "exp": FAR_FUTURE, **claims}
        return httpx.Response(200, json=claims)


@pytest.fixture
def introspection():
    return FakeIntrospection()


@pytest.fixture
async def app(introspection):
    api = httpx.MockTransport(lambda request: httpx.Response(200, json=NOTE))
    server = create_server(
        Config("http://api.test/api", TOKEN),
        transport=api,
        auth=oauth_provider(
            HTTP, httpx.AsyncClient(transport=httpx.MockTransport(introspection.handler))
        ),
    )
    app = server.http_app(**http_options(HTTP))
    async with app.router.lifespan_context(app):
        yield app


def raw(app, host: str = "myfilaments.dev") -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url=f"https://{host}")


def mcp_client(app, token: str) -> Client:
    def factory(**kwargs):
        return httpx2.AsyncClient(transport=httpx2.ASGITransport(app=app), **kwargs)

    return Client(StreamableHttpTransport(RESOURCE, auth=token, httpx_client_factory=factory))


INITIALIZE = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}
ACCEPT = {"Accept": "application/json, text/event-stream"}


async def test_no_token_gets_401_with_the_challenge(app):
    async with raw(app) as client:
        response = await client.post("/mcp", json=INITIALIZE, headers=ACCEPT)

    assert response.status_code == 401
    challenge = response.headers["www-authenticate"]
    assert challenge.startswith("Bearer ")
    assert f'resource_metadata="{PUBLIC}/.well-known/oauth-protected-resource/mcp"' in challenge


async def test_protected_resource_metadata(app):
    async with raw(app) as client:
        data = (await client.get("/.well-known/oauth-protected-resource/mcp")).json()

    assert data["resource"] == RESOURCE
    assert data["authorization_servers"] == [PUBLIC]
    assert data["scopes_supported"] == ["notes"]


async def test_valid_token_reaches_the_tools(app, introspection):
    async with mcp_client(app, "good") as client:
        reply = (await client.call_tool("get_filament", {"id": NOTE["id"]})).content[0].text

    assert reply.startswith('"Album cover ideas"')
    # Introspection used the MCP client's own credentials (HTTP Basic).
    expected = "Basic " + base64.b64encode(b"mcp-client:mcp-secret").decode()
    assert introspection.calls[0].headers["Authorization"] == expected


@pytest.mark.parametrize("token", ["wrong-scope", "wrong-audience", "inactive", "unknown"])
async def test_bad_tokens_are_refused(app, token):
    async with raw(app) as client:
        response = await client.post(
            "/mcp", json=INITIALIZE, headers=ACCEPT | {"Authorization": f"Bearer {token}"}
        )

    assert response.status_code == 401


async def test_every_request_is_checked_so_revocation_is_immediate(app, introspection):
    async with mcp_client(app, "good") as client:
        await client.call_tool("get_filament", {"id": NOTE["id"]})
        calls_before = len(introspection.calls)
        introspection.tokens["good"] = {"active": False}  # revoked in Django

        with pytest.raises(Exception):  # noqa: B017 - any refusal; the transport sees a 401
            await client.call_tool("get_filament", {"id": NOTE["id"]})

    assert len(introspection.calls) > calls_before


async def asgi_status(app, host: str, origin: str | None = None) -> int:
    """Send one request the way uvicorn would inside the container (bound to 0.0.0.0).

    httpx's test transport sets the ASGI `server` to the request's own host, which the
    guard treats as allowed, so it can't test host checks.
    """
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": "/mcp",
        "raw_path": b"/mcp",
        "query_string": b"",
        "headers": [
            (b"host", host.encode()),
            (b"authorization", b"Bearer good"),
            (b"content-type", b"application/json"),
            (b"accept", b"application/json, text/event-stream"),
            *([(b"origin", origin.encode())] if origin else []),
        ],
        "server": ("0.0.0.0", 8000),
        "client": ("172.18.0.5", 40000),
    }
    body = b'{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}'
    sent = False
    status = {}

    async def receive():
        nonlocal sent
        if sent:
            return {"type": "http.disconnect"}
        sent = True
        return {"type": "http.request", "body": body, "more_body": False}

    async def send(message):
        if message["type"] == "http.response.start":
            status["code"] = message["status"]

    await app(scope, receive, send)
    return status["code"]


@pytest.mark.parametrize(
    ("host", "allowed"),
    [("evil.example", False), ("myfilaments.dev", True), ("mcp:8000", True)],
)
async def test_host_guard(app, host, allowed):
    status = await asgi_status(app, host)

    assert (status != 421) is allowed, status


# --- Configuration --------------------------------------------------------------


HTTP_ENV = {
    "FILAMENTS_PUBLIC_URL": "https://myfilaments.dev/",
    "FILAMENTS_INTROSPECTION_CLIENT_ID": "id",
    "FILAMENTS_INTROSPECTION_CLIENT_SECRET": "secret",
}


@pytest.fixture
def http_env(monkeypatch):
    for key in [*HTTP_ENV, "FILAMENTS_INTROSPECTION_URL", "FILAMENTS_ALLOW_INSECURE_PUBLIC_URL"]:
        monkeypatch.delenv(key, raising=False)
    for key, value in HTTP_ENV.items():
        monkeypatch.setenv(key, value)
    return monkeypatch


def test_http_config_defaults(http_env):
    config = load_http_config()

    assert config.public_url == PUBLIC
    assert config.resource_url == RESOURCE
    assert config.introspection_url == "http://web:8000/o/introspect/"
    assert allowed_hosts(config) == ["myfilaments.dev", "mcp", "myfilaments.dev:*", "mcp:*"]


@pytest.mark.parametrize(
    "missing",
    [
        "FILAMENTS_PUBLIC_URL",
        "FILAMENTS_INTROSPECTION_CLIENT_ID",
        "FILAMENTS_INTROSPECTION_CLIENT_SECRET",
    ],
)
def test_missing_setting_names_it(http_env, missing):
    http_env.delenv(missing)

    with pytest.raises(ConfigError, match=missing):
        load_http_config()


def test_public_url_with_a_path_is_refused(http_env):
    http_env.setenv("FILAMENTS_PUBLIC_URL", "https://myfilaments.dev/notes")

    with pytest.raises(ConfigError, match="without a path"):
        load_http_config()


def test_plain_http_public_url_is_refused(http_env):
    http_env.setenv("FILAMENTS_PUBLIC_URL", "http://myfilaments.dev")

    with pytest.raises(ConfigError, match="https://"):
        load_http_config()


def test_plain_http_allowed_only_with_the_explicit_override(http_env):
    http_env.setenv("FILAMENTS_PUBLIC_URL", "http://127.0.0.1:8080")
    http_env.setenv("FILAMENTS_ALLOW_INSECURE_PUBLIC_URL", "true")

    config = load_http_config()

    assert config.public_host == "127.0.0.1:8080"
    assert "127.0.0.1:8080" in allowed_hosts(config)


@pytest.mark.parametrize(
    ("origin", "allowed"),
    [
        (None, True),
        ("https://myfilaments.dev", True),
        ("https://claude.ai", True),
        ("https://evil.example", False),
    ],
)
async def test_origin_guard(app, origin, allowed):
    # Behind the edge, uvicorn sees plain http; a real https Origin must still pass.
    status = await asgi_status(app, "myfilaments.dev", origin)

    assert (status != 403) is allowed, status
