## Context

`api/api.py` creates one `NinjaAPI` with no auth; `api/health.py` already declares `auth=None`. Compose binds the API to `127.0.0.1:8000`. About 40 API tests use pytest-django's bare `client`. Since step 4, the web UI's plan is to call `filaments/services.py` and `filaments/queries.py` in-process, so the MCP server is the API's only caller.

```
 MCP server ── Authorization: Bearer <FILAMENTS_API_TOKEN> ──▶ /api/*       ✓
 no / wrong token ───────────────────────────────────────────▶ /api/*       401 + warning log
 anyone ─────────────────────────────────────────────────────▶ /api/health  ✓ (auth=None)
```

## Goals / Non-Goals

**Goals:**
- Every API route except health requires the token, including routes added later.
- A missing or weak token stops startup rather than leaving the API open.
- Existing tests keep working without per-test changes.

**Non-Goals:**
- OAuth for Claude → MCP (step 8); exposing anything through the tunnel (step 9).
- Multiple tokens, rotation tooling, per-route scopes, rate limiting.
- Protecting `/api/docs` (localhost-only) or changing `/admin` (session login).

## Decisions

### Global auth with an explicit opt-out

`NinjaAPI(auth=ServiceToken())` in `api/api.py`. Ninja applies API-level auth to every operation that doesn't set its own `auth`; health's existing `auth=None` opts out. **Alternative:** `Router(auth=...)` per router. Rejected: a new router added without auth would be silently open.

### `ServiceToken(HttpBearer)` in `api/auth.py`

```python
class ServiceToken(HttpBearer):
    def authenticate(self, request, token):
        if secrets.compare_digest(token.encode(), settings.FILAMENTS_API_TOKEN.encode()):
            return token  # truthy → authenticated; request.auth is set
        return None
```

- Reads `settings` at request time, so tests can override it and nothing is captured at import.
- `compare_digest` avoids timing leaks; bytes are compared so non-ASCII input can't raise.
- `HttpBearer` already rejects a missing header or a non-`Bearer` scheme before `authenticate` runs.

### 401 body and logging

Ninja raises `AuthenticationError` when auth fails; its default handler returns `{"detail": "Unauthorized"}`. Registering `@api.exception_handler(AuthenticationError)` returns `{"detail": "Missing or invalid API token"}` (status 401) and logs `logger.warning("Rejected API request: %s %s", request.method, request.path)`. The `Authorization` header is never logged. Ninja picks handlers by MRO, so this one wins over the generic `Exception` handler from step 4.

### Required, minimum-length setting

In `settings.py`, `FILAMENTS_API_TOKEN = env_token("FILAMENTS_API_TOKEN", min_length=32)`, raising `ImproperlyConfigured` naming the key (never its value) when missing or short. 32 characters matches `secrets.token_urlsafe(32)` (43 characters) with margin, and rejects placeholders like `changeme`. `.env.example` gets the generation command, mirroring `DJANGO_SECRET_KEY`.

### Tests: conftest sets the token and authenticates the default client

`backend/tests/conftest.py`:

- an autouse fixture sets `settings.FILAMENTS_API_TOKEN` to a fixed 40-character test token, so tests never depend on the real `.env` value;
- a `client` fixture overriding pytest-django's returns `Client(headers={"Authorization": f"Bearer {TEST_TOKEN}"})`;
- an `anon_client` fixture returns a bare `Client()` for the 401 tests.

Existing tests keep using `client` unchanged. **Alternative:** add the header in every test. Rejected as noise.

## Risks / Trade-offs

- [Token in `.env` on the laptop] → Same trust boundary as `DJANGO_SECRET_KEY` and the DB password; `.env` is gitignored.
- [Forgetting to set the token in a new environment] → Startup fails loudly with the key name, and the Compose healthcheck shows `web` unhealthy.
- [Overriding pytest-django's `client` fixture surprises a reader] → The conftest docstring says so; `anon_client` makes unauthenticated tests explicit.
- [Ninja serves `/api/docs` and `/api/openapi.json` without auth] → Served only when `DEBUG` is on (found in code review); the laptop deployment returns 404 for both.
- [Ninja's `HttpBearer.__call__` logs the first header word when `DEBUG` is on, which is the token if a caller omits the scheme] → `ServiceToken` overrides `__call__` and parses the header itself with `split(None, 1)` (which also tolerates extra whitespace); nothing from the header is logged. Found in code review; a test with `DEBUG=True` covers it.

## Migration Plan

Generate a token, add `FILAMENTS_API_TOKEN` to `.env`, rebuild `web`. Rollback is reverting the commit (the extra env var is harmless).

## Open Questions

None.
