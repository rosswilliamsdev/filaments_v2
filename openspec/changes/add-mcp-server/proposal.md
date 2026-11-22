## Why

The API (steps 4–6) can store and find filaments, but Claude can't reach it yet. This change adds the MCP server Claude talks to: six tools that call the API with the service token, validate input with the shared schemas, and answer in short sentences that make sense read aloud. It runs over stdio so a local Claude client (Claude Code or Claude Desktop) can exercise every tool before anything goes behind the tunnel (step 9). Phase: **Phase 1 (voice capture)**, roadmap step 7.

## What Changes

- **Framework: FastMCP 4** (the standalone `fastmcp` package, gofastmcp.com), pinned `>=4.2,<5`. It is built on the official MCP SDK and ships ready-made token verifiers (`introspection`, `jwt`) for step 9's deferred decision. **Doc correction:** CLAUDE.md, the PRD, the backend planning doc and the README say "official MCP Python SDK (FastMCP)"; the official SDK's built-in copy was renamed `MCPServer` in SDK 2.0, so they become "FastMCP 4 (gofastmcp.com), built on the official MCP SDK".
- **Deferred decision settled: `list_filaments` and `search_filaments` merge** into one `search_filaments` (all parameters optional; no query lists newest first). This keeps "MCP tools map one-to-one onto API routes" true, since both pointed at `GET /api/filaments`. Six tools:
  - `create_filament(title, body, tags?)` → `POST /api/filaments`
  - `search_filaments(query?, tags?, date_from?, date_to?, limit?, offset?)` → `GET /api/filaments`
  - `get_filament(id)` → `GET /api/filaments/{id}`
  - `update_filament(id, title?, body?, tags?)` → `PATCH /api/filaments/{id}`
  - `delete_filament(id)` → `DELETE /api/filaments/{id}`
  - `list_tags()` → `GET /api/tags`
- New workspace member `mcp_server/` (`filaments-mcp`, import `filaments_mcp`), run with `python -m filaments_mcp` over stdio. Depends on `fastmcp`, `httpx` and `filaments-schemas`; never on Django.
- Tool input is validated **inside** each tool with the shared `schemas` models, so validation and API errors share one plain-language formatter (e.g. "tags: Tag limit is 8; got 9"). Errors are raised as `ToolError`; unexpected exceptions are masked (`mask_error_details=True`) and logged to stderr.
- **Voice-ready results:** a speakable first sentence, then compact lines; ids appear only in trailing brackets for follow-up calls. Search shows ~200-character excerpts; `get_filament` shows the full body. Times are spoken as e.g. "Tue Nov 24, 11:30 PM" from the API's local timestamps.
- Tool annotations: search, get and `list_tags` read-only; `delete_filament` destructive; server instructions tell Claude to reuse tags via `list_tags`, keep to 8 tags, and not read ids aloud.
- New setting `FILAMENTS_API_URL` (default `http://127.0.0.1:8000/api`); reuses `FILAMENTS_API_TOKEN`.
- **Roadmap change:** the `mcp` Docker Compose service moves to step 9 (a stdio server is launched by its client, not run as a service).

## Capabilities

### New Capabilities
- `mcp-tools`: the six MCP tools, their mapping to API routes, input validation, result wording, error translation, and the stdio entry point.

### Modified Capabilities
- None.

## Impact

- **Code:** new `mcp_server/` package (`config.py`, `api_client.py`, `formatting.py`, `server.py`, `__main__.py`); `schemas` unchanged.
- **Tests:** new `mcp_server/tests/` (formatting, error mapping with `httpx.MockTransport`, tools through FastMCP's in-memory client, a stdio subprocess smoke test) and one end-to-end test in `backend/tests/` driving the tools against pytest-django's `live_server`.
- **Config:** root `pyproject.toml` (workspace member, `testpaths`, Ruff first-party, dev dependency); `FILAMENTS_API_URL` in `.env.example`; CLAUDE.md Commands gains the run and `claude mcp add` commands.
- **Docs:** framework wording (above); six tools in PRD, backend planning doc, roadmap and README; remove the list/search item from Deferred Decisions; PRD's "the same API serves both the web UI and Claude" corrected (the web UI calls the service modules in-process since step 4).
- **Dependencies:** `fastmcp>=4.2,<5` (brings the official `mcp` SDK), `httpx`.

## Open questions

- None blocking. Step 9 decides how the MCP server checks OAuth tokens (introspection vs. JWT); FastMCP has verifiers for both.
