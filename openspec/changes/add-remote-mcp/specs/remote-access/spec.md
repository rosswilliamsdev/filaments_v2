## ADDED Requirements

### Requirement: Only the MCP endpoint and sign-in are public
The `edge` service SHALL be the only service the tunnel reaches. It SHALL forward `/mcp` and `/.well-known/oauth-protected-resource` (and paths under it) to the MCP server; `/.well-known/oauth-authorization-server`, `/o/authorize/`, `/o/token/`, `/o/revoke_token/`, `/accounts/login/` and `/accounts/logout/` to Django; and SHALL answer every other path with 404 without contacting any backend. The allowlist SHALL be kept in version control.

#### Scenario: API unreachable from outside
- **WHEN** a request for `/api/filaments` or `/api/health` arrives through the edge
- **THEN** the response is 404 and Django receives nothing

#### Scenario: Admin and introspection unreachable
- **WHEN** a request for `/admin/` or `/o/introspect/` arrives through the edge
- **THEN** the response is 404

#### Scenario: Sign-in reachable
- **WHEN** a browser opens `/accounts/login/` through the edge
- **THEN** it gets the login page

#### Scenario: Discovery reachable
- **WHEN** a client requests `/.well-known/oauth-authorization-server` through the edge
- **THEN** it gets the authorization server metadata with issuer `https://myfilaments.dev`

### Requirement: The tunnel runs only where it's wanted
The `cloudflared` service SHALL run only when the `public` Compose profile is enabled, SHALL take its credentials from `CLOUDFLARE_TUNNEL_TOKEN` in `.env`, and SHALL be the only service that connects to the internet. No service SHALL publish a port beyond `127.0.0.1`.

#### Scenario: Development machine
- **WHEN** `docker compose up -d` runs without the `public` profile
- **THEN** no tunnel starts and no tunnel token is needed

#### Scenario: Laptop
- **WHEN** `docker compose --profile public up -d` runs with a valid token
- **THEN** `cloudflared` connects and `https://myfilaments.dev` reaches the edge

### Requirement: Django works behind the proxies
When `FILAMENTS_PUBLIC_URL` is an `https` URL, Django SHALL accept its host, trust it as a CSRF origin, treat requests forwarded with `X-Forwarded-Proto: https` as secure, and mark its session and CSRF cookies secure.

#### Scenario: Sign in through the tunnel
- **WHEN** you submit the login form at `https://myfilaments.dev/accounts/login/`
- **THEN** the request passes host and CSRF checks and the session cookie is marked Secure
