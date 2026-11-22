## Why

Steps 4–7 (the API routes and MCP tools) all need the same request and response shapes, and the tag rules have to give the same answer whether a tag comes from Claude, the API or (later) the web UI. Defining them once now, in the Django-free `schemas` package, means the MCP server can validate Claude's input before it makes an HTTP call, and the API and MCP layers can never drift apart. Phase: **Phase 1 (voice capture)**, roadmap step 3.

## What Changes

- Add a pure tag normalization pipeline to `schemas`: trim → lowercase → strip accents → each run of non-letter/non-digit characters (including spaces and `_`) becomes one `-` → trim leading/trailing `-`. Tags that end up empty, or longer than 50 characters, are rejected (not dropped or truncated). Duplicates are removed, keeping first-seen order.
- Enforce the **8-tag limit after normalization and deduplication**, in a validator (not `Field(max_length=8)`), with speakable messages such as "Tag limit is 8; got 10".
- Add the filament shapes: `FilamentCreate`, `FilamentUpdate` (PATCH: omitted = unchanged, `tags: []` clears, `null` title/body rejected), `FilamentOut`, `TagWithCount`, `FilamentListParams` (`q`, `tags`, `date_from`, `date_to`, `limit`, `offset`) and `FilamentList` (`items`, `total`, `limit`, `offset`). All flat, so FastMCP turns them into flat tool arguments.
- `source` is not in any request schema; the server sets it.
- Add a home timezone setting, `FILAMENTS_TIMEZONE` (e.g. `America/Chicago`), read into Django's `TIME_ZONE`. Storage stays UTC (`USE_TZ=True`); date filters (step 5) and returned timestamps use the local day. Added to `.env.example`; Compose already passes `.env` to `web`.
- Add `schemas/tests/` (no database needed) to the pytest run, including a test that importing `schemas` never loads Django.
- **Doc update:** the tag rule in `CLAUDE.md`, `docs/backend-planning-doc.md`, `docs/PRD.md` and `roadmap.md` says "spaces to hyphens"; it becomes the fuller rule above. This extends the documented rule rather than contradicting it, but it changes how tags are stored, so it is called out here.

## Capabilities

### New Capabilities
- `shared-schemas`: the request/response shapes shared by the API and MCP server, tag normalization and the tag limit, PATCH semantics, list parameters, and the rule that `schemas` has no Django dependency.

### Modified Capabilities
- `filament-storage`: adds the requirement that dates are interpreted in a configured home timezone while timestamps are stored in UTC.

## Impact

- **Code:** `schemas/src/schemas/tags.py`, `schemas/src/schemas/filaments.py`, `schemas/src/schemas/__init__.py`; `backend/config/settings.py` (`TIME_ZONE` from env).
- **Tests:** new `schemas/tests/`; root `pyproject.toml` `testpaths` gains `schemas/tests`.
- **Config:** `FILAMENTS_TIMEZONE` in `.env.example` and `.env` (Compose reads it via `env_file`); CLAUDE.md Commands/Domain rules updated.
- **Dependencies:** none new (accent stripping uses the standard library's `unicodedata`; timezones use `zoneinfo`).
- **Not in this change:** the routes that use these shapes (steps 4–5) and applying the timezone to query filters (step 5).

## Open questions

- **Deferred decision (not decided here):** whether `list_filaments` and `search_filaments` stay separate MCP tools or merge (step 7). `FilamentListParams` serves `GET /api/filaments` either way.
- **Deferred to step 4:** where write logic lives (a service module vs. the route functions), which also decides how `source` is set for web UI writes.
