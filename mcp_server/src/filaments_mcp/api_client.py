"""HTTP client for the Filaments API. Every failure becomes a speakable ToolError."""

import logging
from typing import Any

import httpx
from fastmcp.exceptions import ToolError

from filaments_mcp.config import Config
from filaments_mcp.formatting import validation_message

logger = logging.getLogger(__name__)

TIMEOUT_SECONDS = 10
NOT_FOUND = "No note with that id."
UNAUTHORIZED = "The notes server rejected my credentials. Check FILAMENTS_API_TOKEN."
SERVER_ERROR = "The notes server hit an error. It has been logged."
UNREACHABLE = "I can't reach the notes server right now."
MISCONFIGURED = "The notes server address looks wrong. Check FILAMENTS_API_URL."
# The API's own 404 detail for a missing or deleted filament (api/filaments.py).
API_NOT_FOUND_DETAIL = "No filament with that id"


class ApiClient:
    def __init__(self, config: Config, transport: httpx.AsyncBaseTransport | None = None):
        self._config = config
        self._transport = transport  # tests inject httpx.MockTransport

    async def request(
        self,
        method: str,
        path: str,
        *,
        json: Any = None,
        params: dict[str, Any] | None = None,
    ) -> Any:
        """Call `{api_url}/{path}` with the service token; return the parsed JSON body."""
        # A client per call: stdio traffic is one person's tool calls, so connection reuse
        # buys nothing, and there is no lifetime to manage.
        async with httpx.AsyncClient(
            base_url=self._config.api_url + "/",
            headers={"Authorization": f"Bearer {self._config.api_token}"},
            timeout=TIMEOUT_SECONDS,
            transport=self._transport,
        ) as client:
            try:
                response = await client.request(method, path, json=json, params=params)
            # TransportError covers refused connections, timeouts, dropped or reset
            # connections and unsupported URL schemes.
            except httpx.TransportError as exc:
                logger.warning("API unreachable: %s %s (%s)", method, path, type(exc).__name__)
                raise ToolError(UNREACHABLE) from None
        return _parse(response)


def _json(response: httpx.Response) -> Any:
    try:
        return response.json()
    except ValueError:
        return None


def _parse(response: httpx.Response) -> Any:
    status, body = response.status_code, _json(response)
    where = f"{response.request.method} {response.request.url}"
    detail = body.get("detail") if isinstance(body, dict) else None

    if status < 400:
        if body is None:
            logger.error("API returned a non-JSON %s response on %s", status, where)
            raise ToolError(SERVER_ERROR)
        return body
    if status == 422 and isinstance(detail, list):
        raise ToolError(validation_message(detail))
    # Only the API's own "no such filament" is a missing note. Any other 404 (e.g. an HTML
    # page because FILAMENTS_API_URL lacks /api) means the route doesn't exist.
    if status == 404 and detail == API_NOT_FOUND_DETAIL:
        raise ToolError(NOT_FOUND)
    if status == 404:
        logger.error("API route not found: %s. Is FILAMENTS_API_URL right?", where)
        raise ToolError(MISCONFIGURED)
    if status == 401:
        raise ToolError(UNAUTHORIZED)
    logger.error("API error %s on %s", status, where)
    raise ToolError(SERVER_ERROR)
