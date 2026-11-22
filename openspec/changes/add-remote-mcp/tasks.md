## 1. MCP over HTTP

- [x] 1.1 Spike: build the FastMCP HTTP app with `RemoteAuthProvider` + `IntrospectionTokenVerifier` and record the exact protected-resource metadata path(s), the `resource` value and the `WWW-Authenticate` header
- [x] 1.2 Extend `config.py` for HTTP mode (`FILAMENTS_PUBLIC_URL` https unless the insecure override, introspection client ID/secret, introspection URL default) with clear errors; add `--http` to `__main__.py` (stdio unchanged)
- [x] 1.3 Attach auth in `create_server` for HTTP mode (scope `notes`, audience `<public>/mcp`, no cache) and set allowed hosts
- [x] 1.4 Tests with a fake introspection endpoint: no token → 401 + challenge; metadata contents; wrong scope, wrong audience, inactive → 401; valid → a tool works; config errors
- [x] 1.5 End-to-end test against `live_server`: real OAuth token (authorize → token with `resource`), MCP over HTTP saves a note; revoked token refused on the next call

## 2. Django behind the proxies

- [x] 2.1 Derive `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, `SECURE_PROXY_SSL_HEADER` and secure cookies from `FILAMENTS_PUBLIC_URL`; tests
- [x] 2.2 `client_ip()` prefers `CF-Connecting-IP`; tests for two tunnel visitors and a local request

## 3. Edge, tunnel and Compose

- [x] 3.1 Add `edge/Caddyfile` (allowlist, 404 default, Cloudflare headers passed through)
- [x] 3.2 Add `mcp_server/Dockerfile`; add `mcp`, `edge` and `cloudflared` (profile `public`) to `compose.yaml` with pinned images; add `CLOUDFLARE_TUNNEL_TOKEN` to `.env.example`
- [x] 3.3 Bring the stack up on the Mac (no profile) and curl the edge: `/api/health`, `/api/filaments`, `/admin/`, `/o/introspect/`, `/random` → 404; `/accounts/login/` → login page; both `.well-known` documents served; `/mcp` without a token → 401 with the challenge; record the results
  - Result (2026-11-22), `--profile remote` on the Mac with `FILAMENTS_PUBLIC_URL=http://127.0.0.1:8080` and a temporary account and clients (all removed afterwards, `.env` restored): `/api/health`, `/api/filaments` (even with the valid service token), `/api/tags`, `/api/docs`, `/admin/`, `/admin/login/`, `/o/introspect/`, `/o/applications/`, `/o/authorize` (no slash), `/accounts/`, `/`, `/random` → **404 at the edge**. `/accounts/login/` → 200; both `.well-known` documents served with the edge's URLs; `/mcp` without a token → 401 `Bearer scope="notes", resource_metadata=".../.well-known/oauth-protected-resource/mcp"`. Then Claude's whole path through the edge: discovery → sign-in → code → token (1 h, scope `notes`, bound to `/mcp`) → MCP `create_filament`, `search_filaments`, `delete_filament` → fake token 401.
  - Found a bug here that the tests couldn't: Django rejected `Host: web:8000` (the mcp container's calls) with 400, so introspection failed. Django now always allows its Docker service name `web`.

## 4. Docs and checks

- [x] 4.1 Remove the domain Deferred Decision; update CLAUDE.md (services, profile, env vars, commands, status), README, backend planning doc and roadmap step 9; write the Cloudflare tunnel and claude.ai connector setup steps
- [x] 4.2 Run `uv run --env-file .env pytest` and `uv run ruff check . && uv run ruff format .`
- [x] 4.3 Run one round of `/code-review` and fix verified findings (per CLAUDE.md)
  - Eight findings. Fixed with tests: Origin guard rejected https origins (reproduced); proxy SSL header trusted on plain-http sites; direct sign-in landed on a blocked `/admin/`; `/mcp/` blocked; public URL with a path accepted; two `.env.example` gaps. Edge re-tested with curl after the Caddyfile edit. Raised with the user rather than changed: per-address lockout doesn't cap guessing spread across many addresses (the step 8 trade-off).
- [ ] 4.4 With you: set up the tunnel on the laptop, add the connector in claude.ai on desktop, save and find a note, confirm a request without a token is rejected; record the result
