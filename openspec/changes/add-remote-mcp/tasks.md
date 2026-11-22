## 1. MCP over HTTP

- [ ] 1.1 Spike: build the FastMCP HTTP app with `RemoteAuthProvider` + `IntrospectionTokenVerifier` and record the exact protected-resource metadata path(s), the `resource` value and the `WWW-Authenticate` header
- [ ] 1.2 Extend `config.py` for HTTP mode (`FILAMENTS_PUBLIC_URL` https unless the insecure override, introspection client ID/secret, introspection URL default) with clear errors; add `--http` to `__main__.py` (stdio unchanged)
- [ ] 1.3 Attach auth in `create_server` for HTTP mode (scope `notes`, audience `<public>/mcp`, no cache) and set allowed hosts
- [ ] 1.4 Tests with a fake introspection endpoint: no token → 401 + challenge; metadata contents; wrong scope, wrong audience, inactive → 401; valid → a tool works; config errors
- [ ] 1.5 End-to-end test against `live_server`: real OAuth token (authorize → token with `resource`), MCP over HTTP saves a note; revoked token refused on the next call

## 2. Django behind the proxies

- [ ] 2.1 Derive `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, `SECURE_PROXY_SSL_HEADER` and secure cookies from `FILAMENTS_PUBLIC_URL`; tests
- [ ] 2.2 `client_ip()` prefers `CF-Connecting-IP`; tests for two tunnel visitors and a local request

## 3. Edge, tunnel and Compose

- [ ] 3.1 Add `edge/Caddyfile` (allowlist, 404 default, Cloudflare headers passed through)
- [ ] 3.2 Add `mcp_server/Dockerfile`; add `mcp`, `edge` and `cloudflared` (profile `public`) to `compose.yaml` with pinned images; add `CLOUDFLARE_TUNNEL_TOKEN` to `.env.example`
- [ ] 3.3 Bring the stack up on the Mac (no profile) and curl the edge: `/api/health`, `/api/filaments`, `/admin/`, `/o/introspect/`, `/random` → 404; `/accounts/login/` → login page; both `.well-known` documents served; `/mcp` without a token → 401 with the challenge; record the results

## 4. Docs and checks

- [ ] 4.1 Remove the domain Deferred Decision; update CLAUDE.md (services, profile, env vars, commands, status), README, backend planning doc and roadmap step 9; write the Cloudflare tunnel and claude.ai connector setup steps
- [ ] 4.2 Run `uv run --env-file .env pytest` and `uv run ruff check . && uv run ruff format .`
- [ ] 4.3 Run one round of `/code-review` and fix verified findings (per CLAUDE.md)
- [ ] 4.4 With you: set up the tunnel on the laptop, add the connector in claude.ai on desktop, save and find a note, confirm a request without a token is rejected; record the result
