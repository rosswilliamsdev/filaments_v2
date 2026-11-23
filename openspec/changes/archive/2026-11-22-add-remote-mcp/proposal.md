## Why

Filaments only matters if Claude can reach it from anywhere: the phone during dictation, any computer. Steps 7 and 8 built the MCP server (stdio only) and the OAuth server (local only). This change exposes exactly the MCP endpoint and the sign-in pages at `https://myfilaments.dev` through a Cloudflare Tunnel, with every MCP request checked against Django by introspection. Phase: **Phase 1 (voice capture)**, roadmap step 9.

## What Changes

- **Deferred decision settled: the domain is `myfilaments.dev`** (bought at Cloudflare). Everything lives on that one host: the connector URL is `https://myfilaments.dev/mcp`, sign-in is `/accounts/login/`, and the OAuth issuer is the bare domain.
- **MCP over HTTP:** `python -m filaments_mcp --http` serves Streamable HTTP at `/mcp` (port 8000) in a new `mcp` Compose service. It requires OAuth on every request: `RemoteAuthProvider` publishes RFC 9728 protected-resource metadata and answers unauthenticated requests with `401` + `WWW-Authenticate`; `IntrospectionTokenVerifier` checks each token at `http://web:8000/o/introspect/` (Docker network only), requiring scope `notes` and `aud` = `https://myfilaments.dev/mcp`, with **no caching** so revocation is immediate. HTTP mode refuses to start without an `https` public URL and the introspection credentials. stdio stays as the unauthenticated local dev harness.
- **An `edge` service (Caddy, pinned)** is the only thing the tunnel reaches. Its allowlist, in `edge/Caddyfile` under version control, routes `/mcp`, `/.well-known/oauth-protected-resource*` to `mcp`, and `/.well-known/oauth-authorization-server`, `/o/authorize/`, `/o/token/`, `/o/revoke_token/`, `/accounts/login/`, `/accounts/logout/` to `web`; **everything else returns 404**, including `/api/`, `/admin/` and `/o/introspect/`. Published on `127.0.0.1:8080` so the rules can be tested with curl before anything is public.
- **A `cloudflared` service (pinned)** behind a `public` Compose profile, so only the laptop runs the tunnel. It reads `CLOUDFLARE_TUNNEL_TOKEN` from `.env`; the tunnel's single public hostname points at `http://edge:80`.
- **Django behind the proxies:** `myfilaments.dev` added to allowed hosts and CSRF trusted origins from `FILAMENTS_PUBLIC_URL`; `SECURE_PROXY_SSL_HEADER`; secure session and CSRF cookies when the public URL is `https`; the login lockout uses the visitor's address from `CF-Connecting-IP`.
- **Docs:** the domain Deferred Decision is removed; CLAUDE.md, the README and the backend planning doc describe the services, the profile, and the Cloudflare and claude.ai setup steps.

## Capabilities

### New Capabilities
- `remote-access`: the public surface: the edge allowlist, the tunnel and its profile, and Django's settings behind the proxies.

### Modified Capabilities
- `mcp-tools`: adds the HTTP transport with mandatory OAuth (protected-resource metadata, 401 challenge, introspection with scope and audience checks).
- `oauth-server`: the login lockout counts the visitor's real address behind the tunnel.

## Impact

- **Code:** `mcp_server/` (`--http` mode, auth wiring, config for public URL and introspection credentials), new `mcp_server/Dockerfile`; new `edge/Caddyfile`; `compose.yaml` (`mcp`, `edge`, `cloudflared`); `backend/config/settings.py` (hosts, CSRF origins, proxy SSL header, secure cookies); `backend/accounts/throttle.py` (`CF-Connecting-IP`).
- **Tests:** MCP HTTP auth (no token → 401 with `resource_metadata`; wrong scope, wrong audience, inactive token → 401; valid → tools work) against a fake introspection endpoint and end to end against `live_server`; edge routing checked with curl against the running Compose stack; Django proxy settings and lockout IP.
- **Config:** `CLOUDFLARE_TUNNEL_TOKEN` in `.env.example`; laptop `.env` sets `FILAMENTS_PUBLIC_URL=https://myfilaments.dev`, `DJANGO_DEBUG=false`, the introspection client ID/secret.
- **Dependencies:** Docker images `caddy:2.11.9` and `cloudflare/cloudflared:2026.10.7`. No new Python packages.
- **Manual steps (yours, after the code):** create the tunnel in Cloudflare Zero Trust and paste its token; add the hostname → `http://edge:80`; add the connector in claude.ai with the Claude client ID and secret.

## Open questions

- None blocking. If claude.ai's connector setup reports a redirect mismatch, it may also use a `claude.com` callback (open since step 8); adding it is one line.
