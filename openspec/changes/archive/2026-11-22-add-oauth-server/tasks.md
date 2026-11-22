## 1. Install and configure

- [x] 1.1 Add `django-oauth-toolkit>=3.4,<4` to the backend; `uv sync`; add `oauth2_provider` and a new `accounts` app to `INSTALLED_APPS`
- [x] 1.2 Add `env_url()` and `FILAMENTS_PUBLIC_URL` (default `http://127.0.0.1:8000`, scheme checked); add `OAUTH2_PROVIDER` settings (scopes, 1 h / 90 d lifetimes, rotation, PKCE, https-only redirects unless DEBUG, issuer, DCR/CIMD off) and `LOGIN_URL`; add `FILAMENTS_PUBLIC_URL` to `.env.example`
- [x] 1.3 Mount RFC 8414 metadata at the root and only authorize/token/revoke_token/introspect under `/o/`; mount `/accounts/login/` and logout

## 2. Login and lockout

- [x] 2.1 Add `LoginThrottle` model and migration in `accounts`
- [x] 2.2 Add `ThrottledLoginView` (10 failures → 5-minute refusal from the last failure, 429 with the plain message, success clears, `select_for_update`, warning logs without passwords) and a phone-friendly `registration/login.html`
- [x] 2.3 Add `backend/tests/test_login_lockout.py`: tenth failure locks even a correct password, expiry after 5 minutes, other IPs unaffected, success resets, password absent from logs

## 3. Clients

- [x] 3.1 Add `setup_oauth_clients` (Claude client and introspection client, hashed secrets printed once, idempotent, `--rotate`, refuses without a superuser)
- [x] 3.2 Test the command: first run creates both and prints secrets, re-run changes nothing, `--rotate` replaces secrets and old ones fail, no superuser → clear error

## 4. OAuth flow tests

- [x] 4.1 Add `backend/tests/test_oauth.py`: metadata contents (issuer, endpoints, S256, no registration endpoint); full flow (signed-out redirect to login, authorize with PKCE and `resource`, code to the Claude callback, token exchange with secret + verifier, `expires_in` 3600, scope `notes`); introspection `active`/`aud`; refresh rotation and old refresh rejected; expired token inactive
- [x] 4.2 Rejections: missing PKCE, wrong redirect URI, wrong verifier, introspection with Claude's credentials or none, `/o/applications/` 404, OAuth token on `/api/filaments` 401

## 5. Docs and checks

- [x] 5.1 Backend planning doc: remove the two OAuth Deferred Decisions (settled), note the login-lockout exception to "no rate limiting", describe the clients and introspection; roadmap step 8 settled; CLAUDE.md Commands (`createsuperuser`, `setup_oauth_clients`), env vars and status
- [x] 5.2 Run `uv run --env-file .env pytest` and `uv run ruff check . && uv run ruff format .`
- [x] 5.3 Rebuild `web` in Docker, run `setup_oauth_clients`, and walk the flow by hand (browser login + curl token exchange + introspection) against `http://127.0.0.1:8000`; record the result
  - Result (2026-11-22), with a temporary `smoke-test` account and clients, deleted afterwards: signed-out authorize → 302 to `/accounts/login/`; login → 302 back to authorize; authorize → 302 to `https://claude.ai/api/mcp/auth_callback` with `code` and `iss=http://127.0.0.1:8000`; token exchange → 200, `expires_in` 3600, scope `notes`, refresh token; introspection (MCP client) → `active: true`, scope `notes`, `aud: ["https://notes.example.com/mcp"]`; the OAuth token on `/api/tags` → 401.
- [x] 5.4 Run one round of `/code-review` and fix verified findings (per CLAUDE.md)
  - Six findings, all verified and fixed with tests: introspection could be reached with Claude's credentials by naming the MCP client in the header (now checks the client DOT authenticated); lockout attempts are counted before the password check (closes the parallel-request race) and refused attempts restart the 5 minutes; empty `REMOTE_ADDR` no longer 500s; introspection keys added to `.env.example`; a direct sign-in lands in the admin.
