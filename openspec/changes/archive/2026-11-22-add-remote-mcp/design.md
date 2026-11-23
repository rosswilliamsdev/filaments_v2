## Context

After steps 7 and 8: the MCP server runs over stdio only (no auth); Django is the OAuth authorization server (pre-registered Claude client, PKCE, resource binding, introspection limited to the MCP client); everything is bound to `127.0.0.1`. The domain `myfilaments.dev` is registered at Cloudflare. FastMCP 4.2.4 provides `IntrospectionTokenVerifier` (introspection URL, client ID/secret via HTTP Basic, `required_scopes`, `audience`, optional cache) and `RemoteAuthProvider` (RFC 9728 metadata pointing at an external authorization server, plus the 401 challenge). Its HTTP app supports `allowed_hosts` and origin protection against DNS rebinding.

```
 claude.ai / phone ──https──▶ myfilaments.dev (Cloudflare: TLS, DDoS)
                                   │ tunnel (outbound from the laptop)
                                   ▼
 cloudflared ──▶ edge:80 (Caddy allowlist) ──┬─▶ mcp:8000   /mcp, /.well-known/oauth-protected-resource*
                  127.0.0.1:8080 for tests   ├─▶ web:8000   /.well-known/oauth-authorization-server, /o/authorize|token|revoke_token/,
                                             │              /accounts/login|logout/
                                             └─▶ 404        everything else (/api/, /admin/, /o/introspect/, …)
 mcp ──▶ web:8000/o/introspect/ (token check)   mcp ──▶ web:8000/api/… (service token)      [Docker network only]
```

## Goals / Non-Goals

**Goals:**
- Claude reaches the MCP server and sign-in pages at `https://myfilaments.dev`, nothing else.
- Every MCP request is authorized by Django, revocation takes effect immediately.
- The public surface is defined in Git and tested with curl before going live.

**Non-Goals:**
- Backups and the soft-delete sweep (step 10); the phone end-to-end acceptance (step 11).
- The Phase 2 web UI (would later be added to the edge allowlist deliberately).
- Cloudflare Access, WAF rules or other paid features.

## Decisions

### Edge allowlist in Caddy, not tunnel rules

`edge/Caddyfile` (image `caddy:2.11.9`) listens on `:80`, with `auto_https off` (Cloudflare terminates TLS). Matchers forward the listed paths to `mcp:8000` or `web:8000` with `reverse_proxy`; a final `respond 404` handles everything else, so blocked paths never reach a backend. Caddy is configured to trust the `cloudflared` hop as a proxy so `X-Forwarded-Proto: https` and `CF-Connecting-IP` from Cloudflare are passed through unchanged. The tunnel has a single public hostname, `myfilaments.dev → http://edge:80`.

**Alternatives:** path rules in Cloudflare's dashboard (not in Git, not testable locally); a locally managed tunnel `config.yml` (in Git, but needs the `cloudflared tunnel login/create` CLI dance and a credentials file). Rejected for C because the firewall should be reviewable and curl-testable before exposure, and your setup shrinks to pasting one token.

### MCP over HTTP with Django introspection

`filaments_mcp.__main__` gains `--http`. In HTTP mode, `config.py` additionally requires `FILAMENTS_PUBLIC_URL` (must be `https://` unless `FILAMENTS_ALLOW_INSECURE_PUBLIC_URL` is set for local tests), `FILAMENTS_INTROSPECTION_CLIENT_ID` and `FILAMENTS_INTROSPECTION_CLIENT_SECRET`, and an optional `FILAMENTS_INTROSPECTION_URL` (default `http://web:8000/o/introspect/`). `create_server(config, auth=...)` attaches:

```python
verifier = IntrospectionTokenVerifier(
    introspection_url=config.introspection_url,
    client_id=...,
    client_secret=...,  # HTTP Basic
    required_scopes=["notes"],
    audience=f"{public_url}/mcp",
    # no cache_ttl_seconds: every request is checked, revocation is immediate
)
auth = RemoteAuthProvider(
    token_verifier=verifier,
    authorization_servers=[public_url],
    base_url=public_url,
    resource_name="Filaments",
)
```

`mcp.run(transport="http", host="0.0.0.0", port=8000, path="/mcp")` with `allowed_hosts=[<public host>, "mcp", "localhost", "127.0.0.1"]`. The stdio path is unchanged and never attaches auth (it's local-only).

**No cache:** one extra request per tool call over the Docker network is negligible for one user; a revoked token stops working on the next request.

**Risk to verify first:** the exact protected-resource metadata path and `resource` value FastMCP publishes (RFC 9728 path-suffixed `/.well-known/oauth-protected-resource/mcp` vs root), so the edge allowlist and the `aud` match what Claude sends. The first test pins them.

### Django behind the proxies

In `settings.py`, derived from `FILAMENTS_PUBLIC_URL`:
- its host is appended to `ALLOWED_HOSTS`, its origin to `CSRF_TRUSTED_ORIGINS`;
- `SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")`;
- `SESSION_COOKIE_SECURE = CSRF_COOKIE_SECURE = True` when it starts with `https://`.

`accounts.throttle.client_ip()` prefers `CF-Connecting-IP`. Trusting the header is safe here: Cloudflare always overwrites it on public traffic, and the only other way to reach `web` is `127.0.0.1` on the laptop itself.

### Compose

- `mcp`: built from new `mcp_server/Dockerfile` (same uv pattern as `backend/Dockerfile`, `--package filaments-mcp`), `command: python -m filaments_mcp --http`, `FILAMENTS_API_URL=http://web:8000/api`, no published port, healthcheck on the protected-resource metadata, `depends_on: web`.
- `edge`: `caddy:2.11.9`, mounts `edge/Caddyfile`, `ports: 127.0.0.1:8080:80`, `depends_on: web, mcp`.
- `cloudflared`: `cloudflare/cloudflared:2026.10.7`, `command: tunnel --no-autoupdate run`, `TUNNEL_TOKEN=${CLOUDFLARE_TUNNEL_TOKEN}`, `profiles: [public]`, `depends_on: edge`. (`mcp` and `edge` are in profiles `remote` and `public`; see "Found during implementation".)

### Found during implementation

- **Profiles:** `mcp` and `edge` need introspection credentials, so a plain `docker compose up` on the Mac would crash-loop `mcp`. They are in profiles `remote` (mcp + edge, for local testing) and `public` (mcp + edge + cloudflared, the laptop); a plain `up` stays db + web.
- **FastMCP's host guard is off by default.** `allowed_hosts` alone does nothing; `host_origin_protection=True` is set in a shared `http_options()` used by both `--http` and the tests. The guard also trusts the ASGI `server` address, which httpx's test transport sets to the request host, so the host test drives the app with a hand-built ASGI scope bound to `0.0.0.0`, as uvicorn is in the container.
- **Django must accept `Host: web`.** The mcp container calls `http://web:8000` for introspection and the API; without `web` in `ALLOWED_HOSTS` Django answered 400 and every token check failed. Found only by the Compose test (unit and live_server tests use `localhost`); Django now always adds `web`.
- **`CF-Connecting-IP` is validated** as an IP address before use; anything else falls back to the connection address.

### Code review (task 4.3)

- **Origin guard rejected https origins.** Behind the edge, uvicorn sees plain http, so FastMCP's same-origin fallback refused any `Origin` header, even `https://myfilaments.dev`; if Claude sends one, every call would fail. `allowed_origins` now lists the public origin, `https://claude.ai` and `https://claude.com` (reproduced and tested; `https://evil.example` still 403).
- **`SECURE_PROXY_SSL_HEADER` only for https sites**, so a forwarded "https" can't fool a plain-http dev server.
- **Direct sign-in landed on a 404** through the tunnel (redirect to `/admin/`, which the edge blocks). It now lands on `/accounts/signed-in/`, allowed by the edge.
- **`/mcp/`** is allowed through the edge (FastMCP answers with a redirect to `/mcp`).
- **A public URL with a path** is rejected by both Django and `--http`: the edge, CSRF origins and the issuer all assume the site root.
- `.env.example`: `FILAMENTS_INTROSPECTION_URL` added; the stale CSRF comment fixed.
- **Not changed, raised with you:** the lockout is per visitor address now that `CF-Connecting-IP` is used, so guessing spread across many addresses isn't capped. That is the per-IP trade-off decided in step 8 (a global lockout would let anyone lock out the only user).

### Verification before going public

1. Unit and integration tests (FastMCP auth against a fake introspection endpoint; end to end against `live_server` with a real OAuth token).
2. `docker compose up -d --build` (no profile) on the Mac with `FILAMENTS_PUBLIC_URL=http://127.0.0.1:8080` and the insecure override, then curl the edge: `/api/health`, `/admin/`, `/o/introspect/` → 404; `/mcp` → 401 with the challenge; metadata documents served.
3. Your Cloudflare and claude.ai steps on the laptop, then the roadmap's "done when".

## Risks / Trade-offs

- [A path added to the edge by mistake exposes it] → Allowlist in Git, a 404 default, and curl checks for the blocked paths in the verification list.
- [Header spoofing of `CF-Connecting-IP`] → Only possible from the laptop itself; Cloudflare overwrites it for everyone else.
- [Tunnel token leak lets someone run a connector for the domain] → Token lives only in the laptop's `.env`; rotate it in the Cloudflare dashboard if exposed.
- [FastMCP metadata path or audience format differs from what Claude sends] → Pinned by the first test; the connector setup error would name the mismatch.
- [Cloudflare outage or laptop offline] → Capture fails and Claude reports "I can't reach the notes server right now." Accepted in the PRD.

## Migration Plan

On the laptop: `git pull`; set `FILAMENTS_PUBLIC_URL=https://myfilaments.dev`, `DJANGO_DEBUG=false`, the introspection pair and `CLOUDFLARE_TUNNEL_TOKEN` in `.env`; `docker compose --profile public up -d --build`; add the connector in claude.ai. Rollback: stop the `public` profile (the tunnel closes) or delete the tunnel in Cloudflare.

## Open Questions

- Whether claude.ai also needs a `claude.com` callback URL (carried from step 8; one-line fix if the connector reports a redirect mismatch).
