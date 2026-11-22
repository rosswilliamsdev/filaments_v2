## ADDED Requirements

### Requirement: HTTP transport requires OAuth on every request
`python -m filaments_mcp --http` SHALL serve the same six tools over Streamable HTTP at `/mcp`. Every request SHALL carry a bearer token that Django's introspection endpoint reports as active, with scope `notes` and `aud` containing `<FILAMENTS_PUBLIC_URL>/mcp`; tokens SHALL be checked on every request, without caching. The server SHALL publish RFC 9728 protected-resource metadata naming `FILAMENTS_PUBLIC_URL` as the authorization server, and SHALL answer a missing or invalid token with `401` and a `WWW-Authenticate` header pointing to that metadata. HTTP mode SHALL refuse to start unless `FILAMENTS_PUBLIC_URL` is `https` and the introspection client ID and secret are set. It SHALL accept requests only for the public host (or the Docker service name), and requests carrying an `Origin` header only from the public origin, `https://claude.ai` or `https://claude.com`.

#### Scenario: No token
- **WHEN** a client calls `/mcp` without a token
- **THEN** the response is 401 with `WWW-Authenticate` naming the protected-resource metadata URL

#### Scenario: Discovery
- **WHEN** a client requests the protected-resource metadata
- **THEN** it lists `https://myfilaments.dev` as the authorization server and the resource as `https://myfilaments.dev/mcp`

#### Scenario: Valid token
- **WHEN** Claude calls `create_filament` with an active token, scope `notes` and the right audience
- **THEN** the note is saved and the speakable reply comes back

#### Scenario: Token for another resource
- **WHEN** a token is active but its `aud` is a different URL
- **THEN** the request is refused with 401

#### Scenario: Revoked token
- **WHEN** a token is revoked in Django and used again
- **THEN** the very next request is refused with 401

#### Scenario: Misconfigured HTTP mode
- **WHEN** `--http` starts without the introspection credentials or with an `http://` public URL
- **THEN** it exits with an error naming the missing or invalid setting
