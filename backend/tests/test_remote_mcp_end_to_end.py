"""Claude's whole remote path, minus the tunnel: a real OAuth token from Django, used
against the MCP server over Streamable HTTP, checked by real introspection.

See the openspec mcp-tools and oauth-server specs.
"""

import httpx
import httpx2
import pytest
from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport
from oauth_helpers import CLAUDE, MCP_INTROSPECTION, exchange, get_code, pkce, sign_in

from filaments_mcp.config import Config, HttpConfig
from filaments_mcp.server import create_server, http_options, oauth_provider

PUBLIC = "https://myfilaments.dev"
RESOURCE = f"{PUBLIC}/mcp"


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def claude_token(live_server, anon_client, oauth_clients) -> str:
    """Sign in and run the code flow exactly as Claude would, bound to the MCP resource."""
    client_id, secret = oauth_clients[CLAUDE]
    verifier, challenge = pkce()
    sign_in(anon_client)
    code = get_code(anon_client, client_id, challenge, resource=RESOURCE)
    response = exchange(anon_client, client_id, secret, code, verifier, resource=RESOURCE)
    assert response.status_code == 200, response.content
    return response.json()["access_token"]


@pytest.fixture
async def mcp_app(live_server, oauth_clients, api_token):
    http = HttpConfig(PUBLIC, f"{live_server.url}/o/introspect/", *oauth_clients[MCP_INTROSPECTION])
    server = create_server(Config(f"{live_server.url}/api", api_token), auth=oauth_provider(http))
    app = server.http_app(**http_options(http))
    async with app.router.lifespan_context(app):
        yield app


def connect(app, token: str) -> Client:
    def factory(**kwargs):
        return httpx2.AsyncClient(transport=httpx2.ASGITransport(app=app), **kwargs)

    return Client(StreamableHttpTransport(RESOURCE, auth=token, httpx_client_factory=factory))


async def call(client, tool, **arguments) -> str:
    return (await client.call_tool(tool, arguments)).content[0].text


@pytest.mark.anyio
async def test_claude_saves_and_finds_a_note_over_http(mcp_app, claude_token):
    async with connect(mcp_app, claude_token) as client:
        saved = await call(client, "create_filament", title="Remote note", body="Saved over HTTP")
        found = await call(client, "search_filaments", query="HTTP")

    assert saved.startswith('Saved "Remote note" with no tags.')
    assert found.startswith("Found 1 note:")


@pytest.mark.anyio
async def test_revoked_token_is_refused_on_the_next_call(
    mcp_app, claude_token, live_server, oauth_clients
):
    client_id, secret = oauth_clients[CLAUDE]

    async with connect(mcp_app, claude_token) as client:
        await call(client, "list_tags")
        # Revoke over real HTTP, as Claude would (not the Django test client: async test).
        async with httpx.AsyncClient() as http:
            revoked = await http.post(
                f"{live_server.url}/o/revoke_token/",
                data={"token": claude_token, "client_id": client_id, "client_secret": secret},
            )
        assert revoked.status_code == 200

        with pytest.raises(Exception):  # noqa: B017 - the transport sees a 401
            await call(client, "list_tags")


@pytest.fixture
def other_resource_token(live_server, anon_client, oauth_clients) -> str:
    """A valid token, but bound to some other server."""
    client_id, secret = oauth_clients[CLAUDE]
    verifier, challenge = pkce()
    sign_in(anon_client)
    other = "https://other.example/mcp"
    code = get_code(anon_client, client_id, challenge, resource=other)
    response = exchange(anon_client, client_id, secret, code, verifier, resource=other)
    return response.json()["access_token"]


@pytest.mark.anyio
async def test_token_for_another_resource_is_refused(mcp_app, other_resource_token):
    with pytest.raises(Exception):  # noqa: B017 - refused at connect time (401)
        async with connect(mcp_app, other_resource_token) as client:
            await call(client, "list_tags")
