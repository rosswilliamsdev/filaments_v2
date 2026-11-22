"""The FastMCP server: six tools, one per API route.

Tool parameters are plain, described types so the published schema stays flat. Input is
validated inside each tool with the shared `schemas` models, so validation failures and
API 422s go through the same plain-language formatter instead of the framework's own
error text. FastMCP is only used in this module.
"""

import uuid
from typing import Annotated, Any

import httpx
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from pydantic import BaseModel, Field, ValidationError

from filaments_mcp import formatting
from filaments_mcp.api_client import NOT_FOUND, ApiClient
from filaments_mcp.config import Config
from schemas import MAX_TAGS, FilamentCreate, FilamentListParams, FilamentUpdate

INSTRUCTIONS = f"""\
Filaments is the user's private notes store. Save what they dictate as a note with a short
title, a Markdown body and tags; find notes again by keyword, tag and date.
- Before choosing tags, call list_tags and reuse existing tags where they fit.
  Use at most {MAX_TAGS} tags; they are normalized to lowercase-with-hyphens.
- Dates are the user's local calendar days, written YYYY-MM-DD.
- Only delete a note when the user explicitly asks.
- Replies end with an id in brackets for follow-up calls. Never read ids aloud.
"""

# MCP's destructiveHint defaults to true for tools that aren't read-only, so set it on
# every writing tool. Saving must never look destructive (no confirmation for a capture);
# updating overwrites text with no history, so it is marked destructive on purpose.
READ_ONLY = {"readOnlyHint": True, "openWorldHint": False}
CREATES = {"readOnlyHint": False, "destructiveHint": False, "openWorldHint": False}
OVERWRITES = {
    "readOnlyHint": False,
    "destructiveHint": True,
    "idempotentHint": True,
    "openWorldHint": False,
}
DELETES = {"readOnlyHint": False, "destructiveHint": True, "openWorldHint": False}


def _describe(model: type[BaseModel], field: str, extra: str = "") -> str:
    """A tool parameter's description, taken from the shared schema so the two can't drift."""
    description = model.model_fields[field].description or ""
    return f"{description} {extra}".strip()


Id = Annotated[str, Field(description="The note's id, from the [id …] in an earlier reply.")]
TagList = Annotated[
    list[str] | None,
    Field(description=_describe(FilamentCreate, "tags", "Reuse existing tags from list_tags.")),
]


def _validated[M: BaseModel](model: type[M], **fields: Any) -> M:
    try:
        return model(**fields)
    except ValidationError as exc:
        raise ToolError(formatting.validation_message(exc.errors())) from None


def _note_path(note_id: str) -> str:
    # Parse the id so nothing but a UUID can reach the URL path (e.g. "../tags").
    try:
        return f"filaments/{uuid.UUID(note_id.strip())}"
    except ValueError:
        raise ToolError(NOT_FOUND) from None


def create_server(config: Config, transport: httpx.AsyncBaseTransport | None = None) -> FastMCP:
    """Build the server. `transport` lets tests replace the HTTP API with a fake."""
    api = ApiClient(config, transport)
    # mask_error_details: an unexpected exception reaches Claude as a generic failure;
    # ToolError messages (ours) still pass through unchanged.
    mcp = FastMCP("filaments", instructions=INSTRUCTIONS, mask_error_details=True)

    @mcp.tool(output_schema=None, annotations=CREATES)
    async def create_filament(
        title: Annotated[str, Field(description=_describe(FilamentCreate, "title"))],
        body: Annotated[str, Field(description=_describe(FilamentCreate, "body"))],
        tags: TagList = None,
    ) -> str:
        """Save a new note. Replies with a one-line confirmation."""
        data = _validated(FilamentCreate, title=title, body=body, tags=tags or [])
        filament = await api.request("POST", "filaments", json=data.model_dump(mode="json"))
        return formatting.saved(filament)

    @mcp.tool(output_schema=None, annotations=READ_ONLY)
    async def search_filaments(
        query: Annotated[
            str | None,
            Field(
                description=(
                    "Keywords matched against titles, bodies and tags. All words must match; "
                    'supports "quoted phrases", -exclusions and "or". Omit to list newest first.'
                )
            ),
        ] = None,
        tags: Annotated[
            list[str] | None, Field(description=_describe(FilamentListParams, "tags"))
        ] = None,
        date_from: Annotated[
            str | None,
            Field(description=_describe(FilamentListParams, "date_from", "Format YYYY-MM-DD.")),
        ] = None,
        date_to: Annotated[
            str | None,
            Field(description=_describe(FilamentListParams, "date_to", "Format YYYY-MM-DD.")),
        ] = None,
        # Default 10, not the API's 20: enough for a spoken answer, lighter on context.
        limit: Annotated[int, Field(description=_describe(FilamentListParams, "limit"))] = 10,
        offset: Annotated[int, Field(description=_describe(FilamentListParams, "offset"))] = 0,
    ) -> str:
        """Find notes by keyword, tag and date, or list the newest. Shows short excerpts;
        use get_filament for a note's full text."""
        params = _validated(
            FilamentListParams,
            q=query,
            tags=tags or [],
            date_from=date_from,
            date_to=date_to,
            limit=limit,
            offset=offset,
        )
        page = await api.request(
            "GET", "filaments", params=params.model_dump(mode="json", exclude_none=True)
        )
        return formatting.search_results(page, has_query=params.q is not None)

    @mcp.tool(output_schema=None, annotations=READ_ONLY)
    async def get_filament(id: Id) -> str:
        """Read one note in full."""
        return formatting.full_filament(await api.request("GET", _note_path(id)))

    @mcp.tool(output_schema=None, annotations=OVERWRITES)
    async def update_filament(
        id: Id,
        title: Annotated[str | None, Field(description="New title. Omit to keep it.")] = None,
        body: Annotated[str | None, Field(description="New body. Omit to keep it.")] = None,
        tags: Annotated[
            list[str] | None,
            Field(description="Replaces all tags; [] removes them. Omit to keep them."),
        ] = None,
    ) -> str:
        """Change a note's title, body or tags. Only the fields you send change."""
        path = _note_path(id)
        sent = {
            name: value
            for name, value in {"title": title, "body": body, "tags": tags}.items()
            if value is not None
        }
        changes = _validated(FilamentUpdate, **sent).changes()
        filament = await api.request("PATCH", path, json=changes)
        return formatting.updated(filament, changes)

    @mcp.tool(output_schema=None, annotations=DELETES)
    async def delete_filament(id: Id) -> str:
        """Delete a note. Only when the user explicitly asks."""
        return formatting.deleted(await api.request("DELETE", _note_path(id)))

    @mcp.tool(output_schema=None, annotations=READ_ONLY)
    async def list_tags() -> str:
        """All tags in use with how many notes have each, most used first."""
        return formatting.tag_counts(await api.request("GET", "tags"))

    return mcp
