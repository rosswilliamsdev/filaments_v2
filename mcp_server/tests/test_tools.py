"""The six MCP tools, called through FastMCP's in-memory client over a fake API.

See the openspec mcp-tools spec.
"""

import httpx
import pytest
from conftest import NOTE, NOTE_ID, TOKEN
from fastmcp.exceptions import ToolError

from filaments_mcp import api_client
from schemas import FilamentCreate, FilamentListParams

pytestmark = pytest.mark.anyio

ID = f"[id {NOTE_ID}]"


async def call(client, tool: str, **arguments) -> str:
    result = await client.call_tool(tool, arguments)
    return result.content[0].text


async def fails(client, tool: str, **arguments) -> str:
    with pytest.raises(ToolError) as exc:
        await client.call_tool(tool, arguments)
    return str(exc.value)


# --- Tool list ------------------------------------------------------------------


async def test_six_tools_with_annotations(mcp_client):
    tools = {tool.name: tool for tool in await mcp_client.list_tools()}

    assert set(tools) == {
        "create_filament",
        "search_filaments",
        "get_filament",
        "update_filament",
        "delete_filament",
        "list_tags",
    }
    for name in ("search_filaments", "get_filament", "list_tags"):
        assert tools[name].annotations.read_only_hint is True
    # destructiveHint defaults to true when unset, so writing tools must say it outright.
    assert tools["create_filament"].annotations.destructive_hint is False
    assert tools["update_filament"].annotations.destructive_hint is True
    assert tools["delete_filament"].annotations.destructive_hint is True
    assert "maxItems" not in str(tools["create_filament"].input_schema)


# --- Create ---------------------------------------------------------------------


async def test_create_sends_normalized_note_with_token(mcp_client, api):
    reply = await call(
        mcp_client,
        "create_filament",
        title="Album cover ideas",
        body="Matte",
        tags=["Music", "design"],
    )

    assert reply == f'Saved "Album cover ideas" with tags design and music. {ID}'
    assert (api.last.method, api.last.url.path) == ("POST", "/api/filaments")
    assert api.last.headers["Authorization"] == f"Bearer {TOKEN}"
    assert api.last_json() == {
        "title": "Album cover ideas",
        "body": "Matte",
        "tags": ["music", "design"],
    }


async def test_create_with_nine_tags_fails_before_any_request(mcp_client, api):
    message = await fails(
        mcp_client, "create_filament", title="t", body="b", tags=[f"t{i}" for i in range(9)]
    )

    assert message == "tags: Tag limit is 8; got 9"
    assert api.requests == []


# --- Search ---------------------------------------------------------------------


async def test_search_sends_params_and_lists_results(mcp_client, api):
    api.body = {"items": [NOTE], "total": 25, "limit": 10, "offset": 0}

    reply = await call(
        mcp_client,
        "search_filaments",
        query="cover",
        tags=["#Music", "design"],
        date_from="2026-11-01",
    )

    params = api.last.url.params
    assert (api.last.method, api.last.url.path) == ("GET", "/api/filaments")
    assert params["q"] == "cover"
    assert params.get_list("tags") == ["music", "design"]
    assert params["date_from"] == "2026-11-01"
    assert params["limit"] == "10"
    assert reply.startswith("Found 25 notes:")
    assert reply.endswith("Showing 1–1 of 25.")


async def test_search_without_query_lists_newest(mcp_client, api):
    api.body = {"items": [NOTE], "total": 1, "limit": 10, "offset": 0}

    reply = await call(mcp_client, "search_filaments")

    assert "q" not in api.last.url.params
    assert reply.startswith("Found 1 note, newest first:")


async def test_search_with_bad_date_names_the_field(mcp_client, api):
    message = await fails(mcp_client, "search_filaments", date_from="next tuesday")

    assert message.startswith("date_from: ")
    assert api.requests == []


# --- Get, update, delete ----------------------------------------------------------


async def test_get_returns_the_full_body(mcp_client, api):
    api.body = {**NOTE, "body": "word " * 100}

    reply = await call(mcp_client, "get_filament", id=NOTE_ID)

    assert api.last.url.path == f"/api/filaments/{NOTE_ID}"
    assert reply.endswith("word " * 100)


async def test_update_sends_only_given_fields(mcp_client, api):
    api.body = {**NOTE, "tags": ["art"]}

    reply = await call(mcp_client, "update_filament", id=NOTE_ID, tags=["Art"])

    assert (api.last.method, api.last.url.path) == ("PATCH", f"/api/filaments/{NOTE_ID}")
    assert api.last_json() == {"tags": ["art"]}
    assert reply == f'Updated "Album cover ideas": tags are now art. {ID}'


async def test_update_with_nothing_fails_before_any_request(mcp_client, api):
    message = await fails(mcp_client, "update_filament", id=NOTE_ID)

    assert message == "Send at least one of title, body or tags"
    assert api.requests == []


async def test_delete(mcp_client, api):
    reply = await call(mcp_client, "delete_filament", id=NOTE_ID)

    assert (api.last.method, api.last.url.path) == ("DELETE", f"/api/filaments/{NOTE_ID}")
    assert reply == 'Deleted "Album cover ideas".'


@pytest.mark.parametrize("bad_id", ["not-a-uuid", "../tags", ""])
async def test_malformed_id_is_not_found_without_a_request(mcp_client, api, bad_id):
    assert await fails(mcp_client, "get_filament", id=bad_id) == "No note with that id."
    assert api.requests == []


async def test_list_tags(mcp_client, api):
    api.body = [{"name": "music", "count": 5}, {"name": "art", "count": 2}]

    assert await call(mcp_client, "list_tags") == "music (5), art (2)"
    assert api.last.url.path == "/api/tags"


async def test_parameter_descriptions_come_from_the_shared_schemas(mcp_client):
    tools = {tool.name: tool for tool in await mcp_client.list_tools()}
    create = tools["create_filament"].input_schema["properties"]
    search = tools["search_filaments"].input_schema["properties"]

    assert create["title"]["description"] == FilamentCreate.model_fields["title"].description
    assert search["limit"]["description"] == FilamentListParams.model_fields["limit"].description


# --- Errors ---------------------------------------------------------------------


@pytest.mark.parametrize(
    ("status", "body", "message"),
    [
        (404, {"detail": "No filament with that id"}, api_client.NOT_FOUND),
        (404, {"detail": "Not Found"}, api_client.MISCONFIGURED),
        (401, {"detail": "Missing or invalid API token"}, api_client.UNAUTHORIZED),
        (500, {"detail": "Something went wrong on the server."}, api_client.SERVER_ERROR),
        (
            422,
            {"detail": [{"loc": ["body", "data", "title"], "msg": "Too long"}]},
            "title: Too long",
        ),
    ],
    ids=["404", "404-wrong-route", "401", "500", "422"],
)
async def test_api_errors_become_speakable(mcp_client, api, status, body, message):
    api.status, api.body = status, body

    assert await fails(mcp_client, "get_filament", id=NOTE_ID) == message


@pytest.mark.parametrize(
    "error",
    [
        httpx.ConnectError("refused"),
        httpx.ReadTimeout("slow"),
        httpx.RemoteProtocolError("connection dropped"),
        httpx.ReadError("reset"),
    ],
    ids=["refused", "timeout", "dropped", "reset"],
)
async def test_unreachable_api(mcp_client, api, error):
    api.error = error

    assert await fails(mcp_client, "list_tags") == api_client.UNREACHABLE


async def test_html_404_means_wrong_api_url(mcp_client, api):
    api.raw = httpx.Response(404, text="<h1>Not Found</h1>")

    assert await fails(mcp_client, "list_tags") == api_client.MISCONFIGURED


async def test_non_json_success_is_a_server_error(mcp_client, api):
    api.raw = httpx.Response(200, text="<html>proxy page</html>")

    assert await fails(mcp_client, "list_tags") == api_client.SERVER_ERROR


async def test_unexpected_errors_are_masked(mcp_client, api):
    api.error = RuntimeError("secret internal detail")

    message = await fails(mcp_client, "list_tags")

    assert "secret internal detail" not in message
