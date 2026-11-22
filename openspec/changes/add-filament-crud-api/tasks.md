## 1. Schema change

- [x] 1.1 Add a `model_validator` to `FilamentUpdate` rejecting an empty update with "Send at least one of title, body or tags"
- [x] 1.2 Update `schemas/tests/test_filaments.py`: replace the empty-update test with a rejection test; keep `changes()` tests passing

## 2. Service module

- [x] 2.1 Create `backend/filaments/services.py` with `create_filament(data, *, source)`, `update_filament(filament, changes)`, `soft_delete_filament(filament)`, each in `transaction.atomic()`, tags via `get_or_create`
- [x] 2.2 Add `backend/tests/test_services.py`: create attaches existing and new tags; update replaces/clears tags; tags-only update moves `updated_at`; a failure while setting tags rolls back the filament row

## 3. API routes

- [x] 3.1 Create `backend/api/filaments.py` with a `filaments` router, a `get_active_filament(str)` helper raising `HttpError(404, "No filament with that id")`, and the POST/GET/PATCH/DELETE routes (source `claude`, DELETE returns the filament)
- [x] 3.2 Mount the router at `/filaments` and add the generic `Exception` handler (log + JSON 500) in `backend/api/api.py`
- [x] 3.3 Add `backend/tests/test_api_filaments.py`, starting with the PATCH test that proves `model_fields_set` survives Ninja (title-only leaves body and tags unchanged)
- [x] 3.4 Cover every scenario in `specs/filament-api/spec.md`: 201 create, tag reuse, `source` ignored, 422 on 9 tags and blank body (nothing stored), get, replace/clear tags, empty PATCH 422, delete then get 404, delete twice 404, soft-deleted 404 on all three routes, malformed id JSON 404, generic 500 with logged traceback

## 4. Docs and checks

- [x] 4.1 `roadmap.md` step 5: `/api/tags` hides tags with zero (non-deleted) filaments; CLAUDE.md layout: note `filaments/services.py` as the home of write logic
- [x] 4.2 Run `uv run --env-file .env pytest` and `uv run ruff check . && uv run ruff format .`; smoke-test the routes against `docker compose up -d --build` with curl
