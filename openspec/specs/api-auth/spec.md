# api-auth Specification

## Purpose
How the API restricts callers to the MCP server: every route except `/api/health` requires the `FILAMENTS_API_TOKEN` bearer token, rejections return a readable 401 and are logged without the token, the OpenAPI docs exist only in development, and the app refuses to start without a strong token.
## Requirements
### Requirement: API routes require the service token
Every API route except `GET /api/health` SHALL require an `Authorization: Bearer <token>` header whose token equals `FILAMENTS_API_TOKEN`. Routes SHALL be protected by default, so a newly added route requires the token unless it explicitly opts out. The comparison SHALL be constant-time. The `Bearer` scheme SHALL be case-insensitive and extra whitespace around the token SHALL be ignored. A 401 SHALL carry the header `WWW-Authenticate: Bearer`.

#### Scenario: Correct token
- **WHEN** the MCP server lists filaments with the correct bearer token
- **THEN** the response is 200

#### Scenario: No token
- **WHEN** a caller lists, creates, gets, updates or deletes filaments, or lists tags, with no `Authorization` header
- **THEN** the response is 401 with `{"detail": "Missing or invalid API token"}` and `WWW-Authenticate: Bearer`, and nothing is read or changed

#### Scenario: Wrong token
- **WHEN** a caller sends a bearer token that differs from `FILAMENTS_API_TOKEN`
- **THEN** the response is 401 with `{"detail": "Missing or invalid API token"}`

#### Scenario: Wrong scheme
- **WHEN** a caller sends the correct token with a scheme other than `Bearer` (e.g. `Token <token>`)
- **THEN** the response is 401

#### Scenario: Extra whitespace
- **WHEN** the MCP server sends `Authorization: Bearer  <token> ` with extra spaces
- **THEN** the response is 200

#### Scenario: Health stays open
- **WHEN** a caller sends `GET /api/health` with no `Authorization` header
- **THEN** the response is 200

### Requirement: Rejected requests are logged without the token
Each rejected request SHALL be logged at warning level with its method and path. The log SHALL NOT contain the presented token or the configured token, including when `DEBUG` is on and the header has no scheme or an unexpected one.

#### Scenario: Misconfigured caller
- **WHEN** a request with a wrong token is rejected
- **THEN** a warning naming the method and path is logged, and neither token value appears in the log

#### Scenario: Token sent without a scheme while debugging
- **WHEN** `DEBUG` is on and a caller sends `Authorization: <token>` with no scheme
- **THEN** the response is 401 and the token does not appear in the log

### Requirement: API docs exist only in development
The OpenAPI docs (`/api/docs`) and schema (`/api/openapi.json`) SHALL be served only when `DEBUG` is on. With `DEBUG` off, as in the laptop deployment, they SHALL return 404, so `/api/health` is the only API path reachable without the token.

#### Scenario: Deployment
- **WHEN** `DEBUG` is off and a caller requests `/api/docs` or `/api/openapi.json`
- **THEN** the response is 404

### Requirement: The token setting is required and strong
The app SHALL refuse to start when `FILAMENTS_API_TOKEN` is missing, empty, or shorter than 32 characters, with an error naming the setting and not echoing its value.

#### Scenario: Missing token
- **WHEN** the app starts without `FILAMENTS_API_TOKEN`
- **THEN** startup fails with an error naming `FILAMENTS_API_TOKEN`

#### Scenario: Placeholder token
- **WHEN** `FILAMENTS_API_TOKEN` is `changeme`
- **THEN** startup fails with an error saying it must be at least 32 characters

