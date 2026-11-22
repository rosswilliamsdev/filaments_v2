## Context

The API is complete for Phase 1's needs: create/get/update/delete, list/search with local-day dates and local timestamps, tags with counts, and a bearer token on every route except health. The `schemas` package (Django-free) defines every request shape. Nothing yet speaks MCP.

```
 Claude Code / Desktop ──spawns──▶ python -m filaments_mcp   (stdio: JSON-RPC on stdin/stdout)
                                     │ validate args with schemas → httpx + Bearer token
                                     ▼
                                   FILAMENTS_API_URL (http://127.0.0.1:8000/api)
                                     │ 2xx → speakable text · 4xx/5xx/conn error → ToolError
                                     ▼
                                   text Claude can read aloud
```

A spike against `fastmcp==4.2.4` confirmed: `ToolError` messages reach the client verbatim; other exceptions leak their message unless `mask_error_details=True` (then "Error calling tool 'x'"); input schemas are strict (`additionalProperties: false`); `annotations={"readOnlyHint": True}` is published; returning `str` adds `{"result": …}` structured content unless `output_schema=None`; `Client(mcp)` runs tools in memory.

## Goals / Non-Goals

**Goals:**
- Six tools, one per API route, usable from a local Claude client over stdio.
- One validation source (`schemas`) and one plain-language error path.
- Replies Claude can read aloud as-is.

**Non-Goals:**
- Streamable HTTP, OAuth token checks, the `mcp` Compose service, the tunnel (steps 8–9).
- MCP resources or prompts; only tools.
- Any change to the API or `schemas`.

## Decisions

### Framework: FastMCP 4, pinned to the major version

`fastmcp>=4.2,<5`. Chosen over the official SDK's `MCPServer` mainly for step 9: `fastmcp.server.auth.providers` has `introspection` and `jwt` verifiers, exactly the two options in that deferred decision. Cost: ~70 installed distributions vs ~36, and a major release roughly every six months; the pin makes upgrades deliberate, and our code stays thin (FastMCP appears only in `server.py`), so moving to `MCPServer` later would mostly be import changes.

### Package layout

```
mcp_server/
  pyproject.toml          # filaments-mcp; deps: fastmcp, httpx, filaments-schemas (workspace)
  src/filaments_mcp/
    __main__.py           # load config, configure stderr logging, mcp.run() (stdio)
    config.py             # FILAMENTS_API_URL (default), FILAMENTS_API_TOKEN (required)
    api_client.py         # async httpx client; maps responses/exceptions to ToolError
    formatting.py         # speakable text: saved/updated/deleted lines, search list, dates, excerpts, errors
    server.py             # FastMCP("filaments", instructions=…, mask_error_details=True) + six tools
  tests/
```

Never named `mcp` (would shadow the SDK), per CLAUDE.md.

### Validation inside the tools, one error formatter

Tool parameters use plain types with `Annotated[..., Field(description=...)]` so the published schema is flat and descriptive. Descriptions are read from the shared models' fields (`_describe()`), so wording can't drift; bounds and defaults stay in the models and are enforced inside the tool (the tool's `limit` default of 10 is the one deliberate difference). Each tool builds the shared model (`FilamentCreate`, `FilamentUpdate`, `FilamentListParams`) and catches `ValidationError`. Pydantic errors and the API's 422 body share the `{loc, msg}` shape, so `formatting.validation_message(errors)` turns either into "tags: Tag limit is 8; got 9" (last `loc` segment that isn't `body`/`query`/`data`; model-level errors without a field are just the message). **Alternative:** annotate parameters with the shared `Annotated` types so the framework validates first. Rejected: its error text ("1 validation error for …Arguments") isn't speakable and we can't reword it.

`update_filament` passes only non-`None` arguments into `FilamentUpdate`, so omitted fields stay omitted and an all-`None` call hits the "Send at least one of title, body or tags" rule.

### API client and error mapping

One `httpx.AsyncClient(base_url=FILAMENTS_API_URL, headers={"Authorization": f"Bearer …"}, timeout=10)`, created per server lifetime. `api_client.request(method, path, json=…, params=…)` returns parsed JSON or raises `ToolError`:

| API outcome | Message |
|---|---|
| 422 | `validation_message(detail)` |
| 404 with the API's `"No filament with that id"` detail | "No note with that id." |
| any other 404 (e.g. URL missing `/api`) | "The notes server address looks wrong. Check FILAMENTS_API_URL." (logged) |
| non-JSON 2xx | the 5xx message (logged) |
| 401 | "The notes server rejected my credentials. Check FILAMENTS_API_TOKEN." |
| 5xx | "The notes server hit an error. It has been logged." |
| any `httpx.TransportError` (refused, timeout, dropped/reset, bad scheme) | "I can't reach the notes server right now." |

`mask_error_details=True` hides anything else from the client; FastMCP logs the traceback to stderr.

### Result wording

- Create: `Saved "Album cover ideas" with tags design and music. [id …]` (tags joined "a, b and c"; "with no tags" when empty).
- Search: `Found 3 notes:` (or `Found 25 notes, newest first:` without a query), then per note `1. "Title" — Tue Nov 24, 11:30 PM — music, design` and an indented excerpt line ending `[id …]`; `Showing 10 of 25.` when `total` exceeds the page. `No notes matched.` when empty.
- Get: title line, date, tags, blank line, full body, `[id …]`.
- Update: `Updated "Title": <what changed>.`, e.g. "tags are now art", "title and body changed".
- Delete: `Deleted "Title".`
- Tags: `music (5), art (2), design (2)` or `No tags yet.`

Dates: `datetime.fromisoformat(api_value)` keeps the API's offset, so `strftime("%a %b %-d, %-I:%M %p")` gives local time without knowing the timezone. Excerpts: collapse whitespace, cut at the last space before 200 characters, add "…". Tools use `output_schema=None` so the text is the whole result.

The tool `limit` default is 10 (the API's is 20): enough for a spoken answer and lighter on Claude's context.

### Server instructions and annotations

`instructions` tell Claude: check `list_tags` and reuse existing tags; at most 8 tags; dates are the user's local days as YYYY-MM-DD; delete only when asked; never read bracketed ids aloud. Annotations: `readOnlyHint` on search/get/list_tags. MCP's `destructiveHint` defaults to true for non-read-only tools, so every writing tool sets it: `false` on create (a capture must never need confirmation), `true` on update (it overwrites text with no history) and delete; `idempotentHint` on update. (Found in code review.)

### Stdio hygiene

Logging is configured to stderr before the server starts; nothing prints to stdout. A missing token exits with status 1 and a stderr message naming the setting.

### Testing

- `mcp_server/tests/test_formatting.py`: dates, excerpts, tag joining, each reply shape, validation-message formatting.
- `mcp_server/tests/test_tools.py`: tools through `fastmcp.Client(mcp)` with the API faked by `httpx.MockTransport` (no new dependency): request method/path/body/params and token header, every error mapping, validation failing before any request, masked unexpected errors, annotations.
- `mcp_server/tests/test_stdio.py`: launch `python -m filaments_mcp` as a subprocess via FastMCP's stdio client and list tools; and the missing-token exit.
- `backend/tests/test_mcp_end_to_end.py`: pytest-django `live_server` with the test token, the tools pointed at it, then create → search → get → update → delete → get (404 message).

Async tests use the `anyio` pytest plugin, which ships with `anyio` (a FastMCP dependency).

## Risks / Trade-offs

- [FastMCP major releases ~every six months] → `<5` pin; FastMCP confined to `server.py`.
- [Bigger dependency tree (~70 packages) in the MCP service] → Only the MCP image carries it; the backend doesn't depend on `filaments-mcp`.
- [Claude reads ids aloud anyway] → Ids only in trailing brackets, plus an explicit instruction.
- [Excerpts hide the part of a note that matched] → Claude can call `get_filament`; highlighting (`ts_headline`) is a later option.
- [End-to-end test needs Django and FastMCP in one process] → It lives in `backend/tests`, which already has Django; `mcp_server/tests` stay Django-free.

## Migration Plan

Additive: new workspace member and env var. To use it locally: `docker compose up -d`, then `claude mcp add filaments -- uv run --env-file <repo>/.env python -m filaments_mcp` (the token stays in `.env`). Rollback: remove the client registration and revert.

## Open Questions

None for this step. Step 9: introspection vs JWT for OAuth token checks.
