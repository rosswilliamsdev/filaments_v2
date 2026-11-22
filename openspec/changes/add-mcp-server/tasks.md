## 1. Package and config

- [x] 1.1 Create `mcp_server/` (`filaments-mcp`, src layout, import `filaments_mcp`) with deps `fastmcp>=4.2,<5`, `httpx`, `filaments-schemas`; add it to the root workspace, dev dependencies, pytest `testpaths` and Ruff `known-first-party`; `uv sync`
- [x] 1.2 Add `config.py` (`FILAMENTS_API_URL` default `http://127.0.0.1:8000/api`, required `FILAMENTS_API_TOKEN`); add `FILAMENTS_API_URL` to `.env.example`

## 2. Formatting and API client

- [x] 2.1 Add `formatting.py`: spoken dates from offset timestamps, ~200-character word-boundary excerpts, tag joining, saved/updated/deleted/search/get/tags replies, and `validation_message()` for Pydantic errors and API 422 bodies
- [x] 2.2 Add `api_client.py`: async httpx client with the bearer token and 10 s timeout; map 422/404/401/5xx and connection errors/timeouts to `ToolError` messages
- [x] 2.3 Add `mcp_server/tests/test_formatting.py`

## 3. Server and tools

- [x] 3.1 Add `server.py`: `FastMCP("filaments", instructions=…, mask_error_details=True)` and the six tools (plain typed, described parameters; validation with the shared schemas inside each tool; `output_schema=None`; read-only/destructive/idempotent annotations)
- [x] 3.2 Add `__main__.py`: stderr logging, config check (exit 1 naming the setting), `mcp.run()` over stdio
- [x] 3.3 Add `mcp_server/tests/test_tools.py` through `fastmcp.Client` with `httpx.MockTransport`: tool list and annotations, each tool's request and reply, token header, every error mapping, validation failing before any request, masked unexpected errors
- [x] 3.4 Add `mcp_server/tests/test_stdio.py`: subprocess over stdio lists six tools; missing token exits non-zero naming the setting

## 4. End to end

- [x] 4.1 Add `backend/tests/test_mcp_end_to_end.py`: `live_server` + test token; create → search → get → update → delete → get gives "No note with that id."

## 5. Docs and checks

- [x] 5.1 Update framework wording ("FastMCP 4 (gofastmcp.com), built on the official MCP SDK") in CLAUDE.md, PRD, backend planning doc and README; six tools everywhere; drop the list/search Deferred Decision; fix PRD's "same API serves both the web UI and Claude"; roadmap step 7 (six tools, no Compose service) and step 9 (adds the `mcp` service); CLAUDE.md Layout/Commands/status (run command, `claude mcp add`)
- [x] 5.2 Run `uv run --env-file .env pytest` and `uv run ruff check . && uv run ruff format .`
- [x] 5.3 Register the server with Claude Code against the running Compose API and create, find, edit and delete a note by chat (the step's "done when"); record the result
  - Result (2026-11-22): covered without a chat client. `backend/tests/test_mcp_end_to_end.py` drives all six tools against the real API (live_server): create → search → get → update → list_tags → delete → get returns "No note with that id." A smoke run of `python -m filaments_mcp` over stdio against the Docker Compose API saved, found and deleted a note with speakable replies and Chicago-time dates. Using it from Claude on any device is steps 8–9 (OAuth + remote MCP over the tunnel); an SSH-based local harness was judged throwaway.
