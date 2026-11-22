"""The MCP tools against the real API (pytest-django's live_server): the whole chain.

Lives in backend/tests because it needs Django; mcp_server/tests stay Django-free.
"""

import re

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

from filaments_mcp.config import Config
from filaments_mcp.server import create_server


@pytest.fixture
def anyio_backend():
    return "asyncio"


async def call(client, tool: str, **arguments) -> str:
    return (await client.call_tool(tool, arguments)).content[0].text


@pytest.mark.anyio
async def test_create_find_edit_delete_through_mcp(live_server, api_token):
    server = create_server(Config(api_url=f"{live_server.url}/api", api_token=api_token))

    async with Client(server) as client:
        saved = await call(
            client,
            "create_filament",
            title="Album cover ideas",
            body="Matte sleeve, hand-drawn type",
            tags=["Music", "design"],
        )
        assert saved.startswith('Saved "Album cover ideas" with tags design and music.')
        note_id = re.search(r"\[id ([0-9a-f-]{36})\]", saved).group(1)

        found = await call(client, "search_filaments", query="sleeve", tags=["music"])
        assert found.startswith("Found 1 note:")
        assert note_id in found

        assert "Matte sleeve, hand-drawn type" in await call(client, "get_filament", id=note_id)

        updated = await call(client, "update_filament", id=note_id, tags=["art"])
        assert updated.startswith('Updated "Album cover ideas": tags are now art.')

        assert await call(client, "list_tags") == "art (1)"

        assert await call(client, "delete_filament", id=note_id) == 'Deleted "Album cover ideas".'

        with pytest.raises(ToolError, match="No note with that id."):
            await client.call_tool("get_filament", {"id": note_id})


@pytest.mark.anyio
async def test_wrong_token_is_reported_plainly(live_server):
    server = create_server(Config(api_url=f"{live_server.url}/api", api_token="wrong-" + "z" * 40))

    async with Client(server) as client:
        with pytest.raises(ToolError, match="rejected my credentials"):
            await client.call_tool("list_tags", {})
