## ADDED Requirements

### Requirement: Authorization server metadata
The system SHALL publish RFC 8414 metadata at `/.well-known/oauth-authorization-server` with `issuer` equal to `FILAMENTS_PUBLIC_URL`, the authorization, token, revocation and introspection endpoints under that issuer, `code_challenge_methods_supported` containing `S256`, `grant_types_supported` including `authorization_code` and `refresh_token`, and `scopes_supported` including `notes`. It SHALL NOT advertise a registration endpoint or client ID metadata document support.

#### Scenario: Claude discovers the server
- **WHEN** a client requests `/.well-known/oauth-authorization-server`
- **THEN** it receives JSON with the issuer, the four endpoints, `S256` in `code_challenge_methods_supported`, and no `registration_endpoint`

### Requirement: Only the needed OAuth endpoints exist
The system SHALL expose authorize, token, revoke and introspect endpoints under `/o/`, and SHALL NOT expose OAuth application-management pages, the device flow, OIDC endpoints or Dynamic Client Registration.

#### Scenario: Management pages absent
- **WHEN** a signed-in user requests `/o/applications/`
- **THEN** the response is 404

### Requirement: Pre-registered clients
`manage.py setup_oauth_clients` SHALL create, if missing, a confidential **Claude** client (authorization-code grant, redirect URI `https://claude.ai/api/mcp/auth_callback`, no consent screen) and a confidential **MCP introspection** client (client-credentials grant), print each new client's ID and secret once, and store secrets hashed. Re-running SHALL NOT change existing clients unless `--rotate` is given, which issues new secrets.

#### Scenario: First run
- **WHEN** the command runs on an empty database
- **THEN** both clients exist and their IDs and secrets are printed

#### Scenario: Re-run is safe
- **WHEN** the command runs again without `--rotate`
- **THEN** no client or secret changes and no secret is printed

#### Scenario: Rotate
- **WHEN** the command runs with `--rotate`
- **THEN** both clients get new secrets, which are printed, and the old secrets stop working

### Requirement: Authorization code flow with PKCE and resource binding
The system SHALL issue authorization codes only to registered clients, only to their exact registered redirect URI, and only with a PKCE `S256` code challenge. A signed-out user SHALL be sent to the login page and returned to the authorization request after signing in. The token endpoint SHALL require the client's credentials and the matching `code_verifier`. A `resource` parameter sent with the request SHALL be recorded on the issued tokens. Tokens SHALL carry the `notes` scope.

#### Scenario: Claude connects
- **WHEN** the Claude client starts authorization with a PKCE S256 challenge and `resource=https://notes.example.com/mcp`, the user signs in, and Claude exchanges the code with its secret and the code verifier
- **THEN** it receives an access token and a refresh token with scope `notes`, and introspection of the access token reports `aud` containing `https://notes.example.com/mcp`

#### Scenario: Missing PKCE
- **WHEN** authorization is requested without a code challenge
- **THEN** no code is issued

#### Scenario: Wrong redirect URI
- **WHEN** authorization is requested with a redirect URI other than the registered one
- **THEN** no code is issued and the user is not redirected to that URI

#### Scenario: Wrong code verifier
- **WHEN** Claude exchanges a valid code with the wrong code verifier
- **THEN** no token is issued

#### Scenario: Signed out
- **WHEN** a signed-out user arrives at the authorization endpoint
- **THEN** they are sent to the login page and, after signing in, the authorization completes

### Requirement: Token lifetimes and refresh rotation
Access tokens SHALL expire 1 hour after issue. Refresh tokens SHALL expire 90 days after issue and SHALL be rotated on every use: each refresh issues a new access token and a new refresh token, and the used refresh token stops working.

#### Scenario: Lifetimes
- **WHEN** Claude receives tokens
- **THEN** `expires_in` is 3600

#### Scenario: Refresh rotates
- **WHEN** Claude uses a refresh token
- **THEN** it receives a new access token and a new refresh token, and reusing the old refresh token fails

### Requirement: Introspection for the MCP server
`/o/introspect/` SHALL accept only the MCP introspection client's credentials and SHALL report for a token: `active`, `scope`, `exp`, `client_id` and, when the token is resource-bound, `aud`. Expired, revoked or unknown tokens SHALL be reported as `active: false`.

#### Scenario: Live token
- **WHEN** the MCP introspection client introspects a live access token
- **THEN** the response has `active: true`, scope `notes` and the bound `aud`

#### Scenario: Expired token
- **WHEN** it introspects an access token past its expiry
- **THEN** the response has `active: false`

#### Scenario: Unauthorized caller
- **WHEN** a request to `/o/introspect/` uses the Claude client's credentials or none
- **THEN** it is rejected

### Requirement: OAuth tokens never authorize the API
Access tokens issued by the authorization server SHALL NOT be accepted by `/api/` routes, which keep requiring the service token.

#### Scenario: OAuth token on the API
- **WHEN** a caller sends an OAuth access token to `GET /api/filaments`
- **THEN** the response is 401

### Requirement: Login page with lockout
The login page SHALL sign the user in with their Django username and password and work on a phone screen. After 10 failed sign-in attempts from one IP address, further attempts from that address SHALL be refused for 5 minutes after the most recent failure, with the message "Too many failed sign-ins. Try again in a few minutes.", even when the password is correct. A successful sign-in SHALL clear that address's count. The count SHALL be shared across all server workers. Failed and refused attempts SHALL be logged with the IP address and username, never the password.

#### Scenario: Tenth failure locks
- **WHEN** an address fails to sign in 10 times
- **THEN** the next attempt from it, even with the correct password, is refused with the lockout message

#### Scenario: Lockout expires
- **WHEN** 5 minutes pass after the last failure
- **THEN** that address can sign in again

#### Scenario: Other addresses unaffected
- **WHEN** one address is locked out
- **THEN** sign-in from another address still works

#### Scenario: Success clears the count
- **WHEN** an address fails 9 times and then signs in successfully
- **THEN** its count resets to zero

#### Scenario: Password never logged
- **WHEN** a sign-in fails
- **THEN** the log names the address and username but not the password

### Requirement: Public URL setting
`FILAMENTS_PUBLIC_URL` SHALL set the issuer and default to `http://127.0.0.1:8000`. Redirect URIs SHALL be required to use `https` unless `DEBUG` is on. A value that does not start with `http://` or `https://` SHALL stop startup with an error naming the setting.

#### Scenario: Bad value
- **WHEN** `FILAMENTS_PUBLIC_URL` is `notes.example.com`
- **THEN** startup fails with an error naming `FILAMENTS_PUBLIC_URL`
