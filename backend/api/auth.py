"""Service-token auth: the MCP server is the API's only caller.

Applied to the whole NinjaAPI, so every route requires the token unless it opts out
with `auth=None` (only /api/health does).
"""

import secrets

from django.conf import settings
from ninja.security import HttpBearer


class ServiceToken(HttpBearer):
    def authenticate(self, request, token: str) -> str | None:
        # Read at request time so tests can override it; compare bytes in constant time
        # (compare_digest raises on non-ASCII str, which would turn a bad token into a 500).
        expected = settings.FILAMENTS_API_TOKEN.encode()
        if secrets.compare_digest(token.encode(), expected):
            return token
        return None
