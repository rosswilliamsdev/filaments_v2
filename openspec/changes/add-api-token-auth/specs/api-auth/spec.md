## ADDED Requirements

### Requirement: API routes require the service token
Every API route except `GET /api/health` SHALL require an `Authorization: Bearer <token>` header whose token equals `FILAMENTS_API_TOKEN`. Routes SHALL be protected by default, so a newly added route requires the token unless it explicitly opts out. The comparison SHALL be constant-time.

#### Scenario: Correct token
- **WHEN** the MCP server lists filaments with the correct bearer token
- **THEN** the response is 200

#### Scenario: No token
- **WHEN** a caller lists, creates, gets, updates or deletes filaments, or lists tags, with no `Authorization` header
- **THEN** the response is 401 with `{"detail": "Missing or invalid API token"}` and nothing is read or changed

#### Scenario: Wrong token
- **WHEN** a caller sends a bearer token that differs from `FILAMENTS_API_TOKEN`
- **THEN** the response is 401 with `{"detail": "Missing or invalid API token"}`

#### Scenario: Wrong scheme
- **WHEN** a caller sends the correct token with a scheme other than `Bearer` (e.g. `Token <token>`)
- **THEN** the response is 401

#### Scenario: Health stays open
- **WHEN** a caller sends `GET /api/health` with no `Authorization` header
- **THEN** the response is 200

### Requirement: Rejected requests are logged without the token
Each rejected request SHALL be logged at warning level with its method and path. The log SHALL NOT contain the presented token or the configured token.

#### Scenario: Misconfigured caller
- **WHEN** a request with a wrong token is rejected
- **THEN** a warning naming the method and path is logged, and neither token value appears in the log

### Requirement: The token setting is required and strong
The app SHALL refuse to start when `FILAMENTS_API_TOKEN` is missing, empty, or shorter than 32 characters, with an error naming the setting and not echoing its value.

#### Scenario: Missing token
- **WHEN** the app starts without `FILAMENTS_API_TOKEN`
- **THEN** startup fails with an error naming `FILAMENTS_API_TOKEN`

#### Scenario: Placeholder token
- **WHEN** `FILAMENTS_API_TOKEN` is `changeme`
- **THEN** startup fails with an error saying it must be at least 32 characters
