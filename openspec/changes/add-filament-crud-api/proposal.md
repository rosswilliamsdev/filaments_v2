## Why

Claude needs to save, read, edit and delete single filaments before search (step 5) or the MCP tools (step 7) can exist. The models (step 2) and shared schemas (step 3) are in place; this change connects them through the HTTP API, with the error behavior the MCP layer will rely on. Phase: **Phase 1 (voice capture)**, roadmap step 4.

## What Changes

- Add a write-logic **service module**, `filaments/services.py`: `create_filament`, `update_filament`, `soft_delete_filament`. Each runs in one transaction, gets-or-creates normalized tags, and takes `source` from its caller. Phase 2 web views will call the same functions in-process.
- Add the API routes on a dedicated `filaments` router:
  - `POST /api/filaments` → 201 + `FilamentOut`; `source` is always `claude` (the API's only caller is the MCP server).
  - `GET /api/filaments/{id}` → 200 + `FilamentOut`.
  - `PATCH /api/filaments/{id}` → 200 + `FilamentOut`; omitted fields unchanged, `tags: []` clears, a tags-only change still moves `updated_at`.
  - `DELETE /api/filaments/{id}` → soft delete, **200 + the filament as it was**, so the MCP tool can say what it deleted.
  - Missing, soft-deleted or malformed ids → 404 `{"detail": "No filament with that id"}`.
- Reject an empty PATCH (`{}`) with a 422 ("Send at least one of title, body or tags"). This lives in `FilamentUpdate` so the MCP server catches it before an HTTP call.
- Add an API-wide handler for unexpected exceptions: log the traceback, return 500 `{"detail": ...}` with a generic message instead of Django's HTML error page.
- Unused tags (no filaments left) are kept; step 5's `/api/tags` will hide zero-count tags. Noted in the roadmap.

## Capabilities

### New Capabilities
- `filament-api`: the create/get/update/delete routes, their status codes and error bodies, single-transaction writes, and the generic 500 handler.

### Modified Capabilities
- `shared-schemas`: `FilamentUpdate` rejects an update that sends no fields.

## Impact

- **Code:** new `backend/filaments/services.py`, `backend/api/filaments.py`; `backend/api/api.py` (router + exception handler); `schemas/src/schemas/filaments.py` (empty-update check).
- **Tests:** new `backend/tests/test_api_filaments.py` and service tests; `schemas/tests/test_filaments.py` updated for the empty-update rule.
- **Docs:** `roadmap.md` step 5 gains "hide zero-count tags"; CLAUDE.md notes the service module.
- **Auth:** routes are unauthenticated until step 6 (the API is bound to localhost and never exposed through the tunnel). The router is separate so step 6 can add `auth=` in one place.
- **Dependencies:** none new.

## Open questions

- None blocking. Not decided here (deferred elsewhere): whether the web UI can create filaments or edit tags (frontend Deferred Decisions); the service functions support both without committing to either.
