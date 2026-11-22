## 1. Setting

- [x] 1.1 In `backend/config/settings.py`, add `env_token()` and `FILAMENTS_API_TOKEN` (required, at least 32 characters, `ImproperlyConfigured` naming the key without echoing the value)
- [x] 1.2 Add `FILAMENTS_API_TOKEN` to `.env.example` with a generation command, and a generated value to the local `.env`
- [x] 1.3 Test `env_token`: missing, empty and short values raise with the key name and without the value; a 43-character token passes

## 2. Auth

- [x] 2.1 Create `backend/api/auth.py` with `ServiceToken(HttpBearer)` (settings read at request time, `secrets.compare_digest` on bytes)
- [x] 2.2 In `backend/api/api.py`, set `auth=ServiceToken()` on the `NinjaAPI` and add an `AuthenticationError` handler returning 401 `{"detail": "Missing or invalid API token"}` with a warning log (method and path only)

## 3. Tests

- [x] 3.1 Create `backend/tests/conftest.py`: autouse test token, authenticated `client` override, `anon_client`
- [x] 3.2 Create `backend/tests/test_api_auth.py`: 401 without a token on every non-health route (list, create, get, patch, delete, tags), 401 on a wrong token and on a non-Bearer scheme, nothing created on a rejected POST, 200 with the token, health 200 without one, the warning is logged and contains neither token
- [x] 3.3 Confirm all existing API tests pass unchanged through the authenticated `client`

## 4. Docs and checks

- [x] 4.1 Fix the roadmap step 6 goal and the backend planning doc so the MCP server is the token's only holder (the web UI calls services in-process); add `FILAMENTS_API_TOKEN` to the CLAUDE.md Commands section and the status line
- [x] 4.2 Run `uv run --env-file .env pytest` and `uv run ruff check . && uv run ruff format .`; rebuild `web` and curl a route with and without the token, and `/api/health` without
