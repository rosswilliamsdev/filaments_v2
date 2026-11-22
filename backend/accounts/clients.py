"""The two pre-registered OAuth clients (created by `manage.py setup_oauth_clients`)."""

from dataclasses import dataclass

from oauth2_provider.models import AbstractApplication

CLAUDE = "claude"
MCP_INTROSPECTION = "filaments-mcp-introspection"
CLAUDE_REDIRECT_URI = "https://claude.ai/api/mcp/auth_callback"


@dataclass(frozen=True)
class ClientSpec:
    name: str
    grant_type: str
    scope: str
    redirect_uris: str = ""
    skip_authorization: bool = False


CLIENTS = [
    # Claude's custom connector ("Use your own OAuth client" in claude.ai). Your own
    # client, so no consent screen; the login page still applies.
    ClientSpec(
        name=CLAUDE,
        grant_type=AbstractApplication.GRANT_AUTHORIZATION_CODE,
        scope="notes",
        redirect_uris=CLAUDE_REDIRECT_URI,
        skip_authorization=True,
    ),
    # The MCP server, to check Claude's tokens at /o/introspect/ (step 9).
    ClientSpec(
        name=MCP_INTROSPECTION,
        grant_type=AbstractApplication.GRANT_CLIENT_CREDENTIALS,
        scope="introspection",
    ),
]

SCOPE_BY_CLIENT = {spec.name: spec.scope for spec in CLIENTS}
