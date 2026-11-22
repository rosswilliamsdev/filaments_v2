"""Fixtures for MCP tool tests: an in-memory MCP client over a fake HTTP API."""

import json

import httpx
import pytest
from fastmcp import Client

from filaments_mcp.config import Config
from filaments_mcp.server import create_server

TOKEN = "test-token-" + "x" * 29
NOTE_ID = "1784d374-fa73-4878-8a5f-4a624b6302a9"
NOTE = {
    "id": NOTE_ID,
    "title": "Album cover ideas",
    "body": "Matte sleeve, hand-drawn type",
    "tags": ["design", "music"],
    "source": "claude",
    "created_at": "2026-11-24T23:30:00-06:00",
    "updated_at": "2026-11-24T23:30:00-06:00",
}


@pytest.fixture
def anyio_backend():
    return "asyncio"


class FakeApi:
    """Records requests and answers with a canned (status, json) or raises an exception."""

    def __init__(self):
        self.requests: list[httpx.Request] = []
        self.status = 200
        self.body: object = NOTE
        self.error: Exception | None = None
        self.raw: httpx.Response | None = None  # e.g. an HTML page instead of JSON

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self.error:
            raise self.error
        if self.raw is not None:
            return self.raw
        return httpx.Response(self.status, json=self.body)

    @property
    def last(self) -> httpx.Request:
        return self.requests[-1]

    def last_json(self) -> object:
        return json.loads(self.last.content)


@pytest.fixture
def api() -> FakeApi:
    return FakeApi()


@pytest.fixture
async def mcp_client(api):
    server = create_server(
        Config(api_url="http://api.test/api", api_token=TOKEN),
        transport=httpx.MockTransport(api.handler),
    )
    async with Client(server) as client:
        yield client
