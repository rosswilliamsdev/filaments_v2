## Context

Claude's custom connectors sign in with OAuth. The MCP authorization spec (2025-11-25) makes the MCP server a resource server and asks the authorization server for: RFC 8414 or OIDC discovery with `code_challenge_methods_supported`, PKCE `S256`, exact redirect-URI matching, HTTPS endpoints, short-lived access tokens, refresh-token rotation, and audience binding through the RFC 8707 `resource` parameter. Claude's help article offers three client options ("Use Claude's published identity", "Register automatically", "Use your own OAuth client") and names one callback, `https://claude.ai/api/mcp/auth_callback`.

django-oauth-toolkit 3.4.1 (checked in its source) ships all of the above: an RFC 8414 metadata view, `PKCE_REQUIRED=True` by default, `resource` stored on grants and tokens and returned as `aud` by introspection, an introspection view guarded by the `introspection` scope, rotation (`ROTATE_REFRESH_TOKEN=True`), hashed client secrets, and optional DCR and CIMD (both off by default).

```
 claude.ai ──1──▶ /.well-known/oauth-authorization-server     (metadata)
           ──2──▶ /o/authorize/ ─▶ /accounts/login/ ─▶ code ─▶ https://claude.ai/api/mcp/auth_callback
           ──3──▶ /o/token/ (code + verifier + secret + resource) ─▶ access (1 h) + refresh (90 d, rotating)
 step 9:  MCP server ──▶ /o/introspect/ (introspection client) ─▶ active, scope, aud
```

## Goals / Non-Goals

**Goals:**
- A working, spec-shaped authorization server inside the existing Django `web` service.
- Nothing extra exposed: no registration, no management UI, no OIDC.
- A login page that is safe to put on the internet in step 9.

**Non-Goals:**
- MCP-side token checks, protected-resource metadata, the tunnel and its domain (step 9).
- Multi-user accounts, social login, 2FA.
- Using OAuth tokens on `/api/` (the API keeps the service token).

## Decisions

### Pre-registered clients, created by a command

`backend/accounts/management/commands/setup_oauth_clients.py` creates two `oauth2_provider.Application` rows, identified by fixed names:

| Name | Type | Grant | Redirect | Scope use | skip_authorization |
|---|---|---|---|---|---|
| `claude` | confidential | authorization-code | `https://claude.ai/api/mcp/auth_callback` | `notes` | yes |
| `filaments-mcp-introspection` | confidential | client-credentials | — | `introspection` | — |

Secrets are generated, printed once, and saved hashed (DOT's default). Existing rows are left alone unless `--rotate`. The Claude client needs a user: the command uses the only superuser, or refuses with "Create your account first: manage.py createsuperuser".

**Alternatives:** CIMD restricted to `claude.ai` (no copy-paste, but an outbound fetch during sign-in that depends on Anthropic's published document); DCR (anyone can register a client). Rejected for this single-user server in favor of the fewest moving parts; both can be switched on later without rework.

`skip_authorization` on Claude's client: the consent screen would ask you to approve your own client every time you connect from a new device. It adds a tap without adding safety.

### Only the needed endpoints

`config/urls.py` mounts DOT's `metadata_urlpatterns` at the root (strict RFC 8414 clients look there) and an explicit list under `/o/`: `authorize/`, `token/`, `revoke_token/`, `introspect/`, taken from DOT's views. It does not include DOT's `urlpatterns` wholesale, which would also publish application management, device flow and OIDC routes.

### Settings

```python
OAUTH2_PROVIDER = {
    "SCOPES": {"notes": "Read and write your notes", "introspection": "Check tokens (MCP server)"},
    "DEFAULT_SCOPES": ["notes"],
    "ACCESS_TOKEN_EXPIRE_SECONDS": 3600,
    "REFRESH_TOKEN_EXPIRE_SECONDS": 90 * 24 * 3600,
    "ROTATE_REFRESH_TOKEN": True,
    "PKCE_REQUIRED": True,
    "ALLOWED_REDIRECT_URI_SCHEMES": ["https"] (+ "http" when DEBUG),
    "OIDC_ISS_ENDPOINT": FILAMENTS_PUBLIC_URL,  # used as the RFC 8414 issuer even with OIDC off
    "DCR_ENABLED": False, "CIMD_ENABLED": False,
}
LOGIN_URL = "/accounts/login/"
```

`FILAMENTS_PUBLIC_URL` is read by an `env_url()` helper (default `http://127.0.0.1:8000`, must start with `http://`/`https://`, trailing slash dropped).

A refresh token's 90 days count from when it was issued; rotation issues a fresh one each use, so regular use never forces a new sign-in.

### Introspection decides the deferred question

DOT access tokens are opaque, so the MCP server checks them by introspection (RFC 7662), not as JWTs: no custom token generator or signing keys. `/o/introspect/` requires a client holding the `introspection` scope; DOT accepts the client's ID and secret as HTTP Basic credentials. Step 9's MCP server calls it over the Docker network and requires `active`, scope `notes`, and its canonical URL in `aud`. FastMCP's `introspection` verifier covers that call.

### Login page and lockout in a new `accounts` app

`accounts.views.ThrottledLoginView` subclasses Django's `LoginView` with a phone-friendly template (`registration/login.html`, plain HTML and a little inline CSS). Throttling uses a small model:

```python
class LoginThrottle(models.Model):
    ip = models.GenericIPAddressField(unique=True)
    failures = models.PositiveIntegerField(default=0)
    last_failure = models.DateTimeField()
```

- Before checking credentials: if `failures >= 10` and `last_failure` is under 5 minutes ago, refuse with the lockout message (status 429) without checking the password.
- On failure: increment (or reset to 1 when the previous lockout window has passed) and set `last_failure`, inside `select_for_update` so concurrent requests can't undercount.
- On success: delete the row.
- Log failures and refusals at warning level with IP and username; never the password.

**Why a model, not the cache:** gunicorn runs two workers, so an in-memory cache would give each worker its own count. A database cache would need `createcachetable` on every deploy. A model is shared, migrated like everything else, and easy to test. **Why not django-axes:** it would be a new dependency for about forty lines of behavior.

**Client IP:** `REMOTE_ADDR` for now. Behind the tunnel (step 9) every request comes from `cloudflared`, so step 9 must take the visitor IP from `CF-Connecting-IP`, trusted only on requests arriving through the tunnel. Recorded here so it isn't lost.

### Templates

Only the login template is needed in normal use (the Claude client skips consent). DOT's default `oauth2_provider/authorize.html` remains for error display. No frontend framework or build step.

## Risks / Trade-offs

- [Login page on the internet guards every note] → Lockout per IP, strong password, Cloudflare in front (step 9), HTTPS-only redirects in production.
- [A lockout per IP doesn't stop guessing spread across many addresses] → Intentional: a global lockout would let anyone lock out the only user. The lockout's job is to slow guessing.
- [Claude may use a `claude.com` callback too] → The redirect list is one line; add it if a connection fails with a redirect mismatch.
- [Issuer must equal the public HTTPS URL in production] → `FILAMENTS_PUBLIC_URL` is set to the tunnel URL in step 9; local tests use `http://` with `DEBUG`.
- [Client secret shown once] → Re-run with `--rotate` to get new ones (Claude's connector must then be updated).
- [DOT 3.x API changes] → Pinned `<4`; DOT appears only in settings, URLs and the setup command.

## Migration Plan

Deploy: rebuild `web` (migrations run on start), `manage.py createsuperuser` if no account exists, `manage.py setup_oauth_clients`, save the printed secrets (Claude's in a password manager until step 9; the introspection pair in `.env`). Rollback: revert; DOT's tables can stay.

## Open Questions

- Whether a `claude.com` callback URL is needed (see Risks).
