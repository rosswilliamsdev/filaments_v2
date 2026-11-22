## Why

To use Filaments from Claude on any device, claude.ai must be able to sign in to the server as a custom connector, and custom connectors use OAuth. This change makes Django the OAuth authorization server: Claude sends you to a login page once, then receives tokens that the MCP server (step 9) will check. Phase: **Phase 1 (voice capture)**, roadmap step 8.

## What Changes

- Install **django-oauth-toolkit 3.4** (already in the decided stack). It covers what the MCP authorization spec (2025-11-25) asks of an authorization server: RFC 8414 metadata with `code_challenge_methods_supported`, PKCE (S256, required), RFC 8707 `resource` binding stored on tokens, token introspection (RFC 7662) and refresh-token rotation.
- Publish only the endpoints needed: `/.well-known/oauth-authorization-server` (at the server root), `/o/authorize/`, `/o/token/`, `/o/revoke_token/`, `/o/introspect/`. No application-management pages, device flow, OIDC, Dynamic Client Registration or CIMD.
- **Client registration: a pre-registered client** ("Use your own OAuth client" in claude.ai). A management command, `setup_oauth_clients`, creates:
  - the **Claude** client: confidential, authorization-code grant, redirect URI `https://claude.ai/api/mcp/auth_callback`, scope `notes`; its ID and secret are printed once to paste into the connector settings;
  - the **MCP server's introspection** client: confidential, client-credentials, scope `introspection`; its ID and secret go in `.env` for step 9.
  Secrets are stored hashed; re-running with `--rotate` issues new ones.
- **Deferred decision settled: tokens are checked by introspection.** DOT issues opaque tokens; the MCP server (step 9) will call `/o/introspect/` over the Docker network and require `active`, scope `notes`, and its own URL in `aud`.
- **Token lifetimes:** access tokens 1 hour; refresh tokens 90 days, rotated on every use.
- **Login page** (`/accounts/login/`, plain Django template, phone-friendly) with a **lockout: 10 failed attempts from one IP address lock that address out for 5 minutes**, counted from the last failure and stored in Postgres so every gunicorn worker shares it. A successful login clears the count. Claude's client skips the consent screen (it is your own pre-registered client).
- New setting **`FILAMENTS_PUBLIC_URL`**, the issuer (default `http://127.0.0.1:8000`; the tunnel URL in step 9). Redirect URIs must be `https` unless `DEBUG` is on.

## Capabilities

### New Capabilities
- `oauth-server`: the authorization server's endpoints and metadata, the pre-registered clients, PKCE and resource binding, token lifetimes and rotation, introspection, and the login page with its lockout.

### Modified Capabilities
- None. The API's service-token auth (`api-auth`) is unchanged: OAuth tokens are for the MCP server, never for `/api/`.

## Impact

- **Code:** new `backend/accounts/` app (login view with lockout, `LoginThrottle` model, `setup_oauth_clients` command, templates); `backend/config/settings.py` (`oauth2_provider`, `accounts`, `OAUTH2_PROVIDER`, login URLs, `FILAMENTS_PUBLIC_URL`); `backend/config/urls.py`.
- **Database:** DOT's migrations and one `accounts` migration (`LoginThrottle`).
- **Tests:** new `backend/tests/test_oauth.py` (the full authorize → login → code → token → introspect flow with PKCE and `resource`, refresh rotation, lifetimes, metadata, rejections) and `backend/tests/test_login_lockout.py`.
- **Config:** `FILAMENTS_PUBLIC_URL` in `.env.example`; CLAUDE.md Commands gains `createsuperuser` and `setup_oauth_clients`.
- **Docs:** the backend planning doc's two OAuth Deferred Decisions are settled and removed; its "no app-level rate limiting" line gains the login-lockout exception; roadmap step 8 updated.
- **Dependencies:** `django-oauth-toolkit>=3.4,<4`.
- **Not in this change (step 9):** the MCP server over HTTP, protected-resource metadata, 401 challenges, the introspection check, the tunnel and its domain, and reading the visitor IP from `CF-Connecting-IP` for the lockout.

## Open questions

- Whether Claude also uses a `claude.com` callback URL. The help article names only `https://claude.ai/api/mcp/auth_callback`; adding a second redirect URI later is a one-line change.
