"""Service-token auth: the MCP server is the API's only caller.

Applied to the whole NinjaAPI, so every route requires the token unless it opts out
with `auth=None` (only /api/health does).
"""

import secrets

from django.conf import settings
from django.http import HttpRequest
from ninja.security import HttpBearer


class ServiceToken(HttpBearer):
    def __call__(self, request: HttpRequest) -> str | None:
        # Parse the header ourselves instead of using HttpBearer.__call__: with DEBUG on,
        # Ninja logs the first word of a non-Bearer header, which is the token itself when
        # a caller sends it without a scheme. Nothing from the header is ever logged here.
        # split(None, 1) also tolerates extra whitespace around the token.
        parts = request.headers.get(self.header, "").split(None, 1)
        if len(parts) != 2 or parts[0].lower() != self.openapi_scheme:
            return None
        return self.authenticate(request, parts[1].strip())

    def authenticate(self, request: HttpRequest, token: str) -> str | None:
        # Read at request time so tests can override it; compare bytes in constant time
        # (compare_digest raises on non-ASCII str, which would turn a bad token into a 500).
        expected = settings.FILAMENTS_API_TOKEN.encode()
        if secrets.compare_digest(token.encode(), expected):
            return token
        return None
