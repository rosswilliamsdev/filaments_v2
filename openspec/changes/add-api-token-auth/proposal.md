## Why

The create/read/update/delete and search routes (steps 4–5) are open to anything on the laptop. Before the MCP server (step 7) starts calling them, and well before anything is reachable through the tunnel (step 9), the API should accept only the MCP server's service token. Phase: **Phase 1 (voice capture)**, roadmap step 6.

## What Changes

- Add a required setting, `FILAMENTS_API_TOKEN`: startup fails if it is missing or shorter than 32 characters, so an empty or placeholder token can never mean "no auth". Added to `.env.example` with a generation command.
- Add a `ServiceToken` Ninja `HttpBearer` auth class that reads the token from settings at request time and compares it with `secrets.compare_digest`.
- Apply it **globally** (`NinjaAPI(auth=ServiceToken())`), so every current and future route requires the token unless it opts out. `/api/health` keeps its explicit `auth=None`.
- A missing, malformed or wrong token returns 401 `{"detail": "Missing or invalid API token"}` and logs a warning with the method and path (never the token).
- Tests: a `conftest.py` sets a known test token and makes the default `client` send it, so existing API tests keep working; new tests cover the 401 cases.
- **Doc fix:** the roadmap says the token is for "the MCP server (and later the web UI)". Since step 4 the web UI calls the service and query modules in-process with session login, so the MCP server is the token's only holder. The roadmap and backend planning doc are updated to say so.

## Capabilities

### New Capabilities
- `api-auth`: the service-token requirement on API routes, the 401 response, and the startup check on the token setting.

### Modified Capabilities
- None. `api-health` already requires that health stays the only unauthenticated route; this change makes that true.

## Impact

- **Code:** new `backend/api/auth.py`; `backend/api/api.py` (global auth); `backend/config/settings.py` (`FILAMENTS_API_TOKEN`).
- **Tests:** new `backend/tests/conftest.py` and `backend/tests/test_api_auth.py`.
- **Config:** `FILAMENTS_API_TOKEN` in `.env.example` and the local `.env`; Compose already passes `.env` to `web` (and will to `mcp` in step 7). CLAUDE.md Commands section notes the new key.
- **Not changed:** `/api/docs` stays available on localhost (its Authorize button accepts the bearer token); `/admin` keeps Django session login.
- **Dependencies:** none new.

## Open questions

- None. Token rotation is manual (edit `.env`, restart `web` and later `mcp`); supporting two valid tokens at once is out of scope.
