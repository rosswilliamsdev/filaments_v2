"""Token introspection, restricted to the MCP server's client.

DOT's IntrospectTokenView accepts the credentials of *any* registered client, so Claude's
client could introspect tokens too. Only the MCP introspection client may.
"""

from oauth2_provider.views import IntrospectTokenView
from oauthlib.common import Request as OauthlibRequest

from accounts.clients import MCP_INTROSPECTION


class McpIntrospectTokenView(IntrospectTokenView):
    def authenticate_client(self, request):
        # Authenticate exactly as DOT does, but keep the oauthlib request so we can see
        # *which* client was authenticated. Re-reading the client id from the request is
        # not enough: a request can name one client in the header and authenticate as
        # another in the body (DOT tries Basic, then falls back to the body).
        core = self.get_oauthlib_core()
        uri, http_method, body, headers = core._extract_params(request)  # DOT 3.x, pinned <4
        oauthlib_request = OauthlibRequest(uri, http_method, body, headers)
        if not core.server.request_validator.authenticate_client(oauthlib_request):
            return False
        client = getattr(oauthlib_request, "client", None)
        # Any other client falls through to DOT's token check, which needs the
        # `introspection` scope, and only the MCP client can get that (accounts.scopes).
        return client is not None and client.name == MCP_INTROSPECTION
