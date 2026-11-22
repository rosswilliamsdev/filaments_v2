## Context

Step 2 gave us `Filament`/`Tag` with DB constraints and a soft-delete default manager; step 3 gave us `FilamentCreate`, `FilamentUpdate` (with `changes()`), and `FilamentOut` (which accepts a related manager for `tags`). `api/api.py` mounts only `/health`. Ninja today lets unhandled exceptions reach Django, which serves an HTML 500 page.

```
 MCP (step 7) ──HTTP──▶ api/filaments.py ──▶ filaments/services.py ──▶ models + DB constraints
                         parse, map errors      one transaction,
 web views (Phase 2) ─────────────────────────▶ tag get-or-create, source from caller
```

## Goals / Non-Goals

**Goals:**
- Create, get, update and soft-delete single filaments over HTTP, with speakable errors.
- Keep write logic callable without HTTP, so Phase 2 views reuse it.
- JSON errors everywhere in the API, including unexpected 500s.

**Non-Goals:**
- List, search and `/api/tags` (step 5); service-token auth (step 6).
- Restoring soft-deleted filaments (admin only), hard deletes (step 10's sweep).
- Web UI create/tag-editing decisions (frontend Deferred Decisions).

## Decisions

### Service module owns the writes

`backend/filaments/services.py`:

```python
def create_filament(data: FilamentCreate, *, source: Filament.Source) -> Filament
def update_filament(filament: Filament, changes: dict) -> Filament
def soft_delete_filament(filament: Filament) -> Filament
```

Each write function is wrapped in `transaction.atomic()`. Tags are attached with `Tag.objects.get_or_create(name=...)`, which already handles the unique-constraint race when Claude makes two parallel tool calls with the same new tag (it retries the get inside a savepoint). `source` is keyword-only with no default, matching the model's "every write path must say where it came from".

`update_filament` sets the sent scalar fields, then always calls `save()` (so `auto_now` moves `updated_at`, including for tags-only updates), then `tags.set(...)` if `tags` was sent.

**Alternative:** logic inside the route functions. Rejected: Phase 2 views would have to call their own HTTP API (which needs the service token) or duplicate the logic.

**Alternative:** `ATOMIC_REQUESTS = True`. Rejected: it covers HTTP only, not services called from views, commands or tests.

### Routes and status codes

`backend/api/filaments.py` holds a `Router(tags=["filaments"])` mounted at `/filaments`; step 6 adds `auth=` there.

| Route | Success | Body |
|---|---|---|
| `POST ""` | 201 | `FilamentOut` |
| `GET "/{filament_id}"` | 200 | `FilamentOut` |
| `PATCH "/{filament_id}"` | 200 | `FilamentOut` |
| `DELETE "/{filament_id}"` | 200 | `FilamentOut` (as it was) |

The API always passes `source=Filament.Source.CLAUDE`: the MCP server is its only caller.

DELETE returns the filament rather than 204 so step 7's tool can say "Deleted 'Album cover ideas'" without an extra GET.

### 404s

A helper `get_active_filament(filament_id: str) -> Filament` parses the id with `uuid.UUID(...)` and looks it up on the default manager (which hides soft-deleted rows); either failure raises `HttpError(404, "No filament with that id")`. The path parameter is typed `str`, not `uuid.UUID`, so a malformed id reaches this code and gets the same JSON 404 instead of a Django URL-resolver 404 (HTML) or a 422 about path format.

Response rows are fetched with `prefetch_related("tags")` so `FilamentOut` reads tags without an extra query per access.

### Empty PATCH rejected in the schema

A `model_validator(mode="after")` on `FilamentUpdate` raises "Send at least one of title, body or tags" when `model_fields_set` is empty. Putting it in `schemas` means the MCP server rejects it before an HTTP call. Ninja reports model-level errors with a `loc` of the body, which still gives Claude the message.

**Risk to verify first:** `changes()` depends on `model_fields_set` surviving Ninja's body parsing. The first PATCH test asserts that `{"title": "x"}` through the HTTP client leaves body and tags unchanged.

### Generic 500 handler

`@api.exception_handler(Exception)` in `api/api.py` logs with `logger.exception(...)` and returns 500 `{"detail": "Something went wrong on the server. It has been logged."}`. Ninja picks handlers by the exception's MRO, so its own handlers for `HttpError`, `ValidationError`, `Http404` and auth errors still win. `DataError`/`IntegrityError` fall through to this handler: the schemas validate first, so reaching the DB constraints means a bug, not bad input.

### Unused tags

Replacing tags can leave a tag with no filaments. It is kept; step 5's `/api/tags` will hide zero-count tags. Deleting orphans during writes would add races for no benefit.

## Risks / Trade-offs

- [`model_fields_set` lost through Ninja] → First PATCH test checks it; fallback is reading the raw JSON keys from `request.body`.
- [Tags-only PATCH writes the row even if nothing visible changed] → Intentional: the user did edit; `updated_at` reflects it.
- [Unauthenticated routes until step 6] → API bound to localhost/Docker network only; nothing in step 4 is exposed through the tunnel (which doesn't exist yet).
- [Generic 500 hides useful detail from Claude] → Intended per CLAUDE.md; the traceback is in `logs/django.log`.

## Migration Plan

No schema migration. Rebuild `web`. Rollback is reverting the commit.

## Open Questions

None blocking.
