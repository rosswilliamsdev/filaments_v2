# api-health Specification

## Purpose
An unauthenticated health route the MCP server, Docker and people can use to check that the API is up and can reach PostgreSQL, plus the guarantee that the stack starts with one command.

## Requirements
### Requirement: Health route reports API and database status
The API SHALL expose `GET /api/health`. It SHALL return HTTP 200 with body `{"status": "ok"}` when the API can query the database, and HTTP 503 with body `{"detail": "Database unavailable"}` when it cannot.

#### Scenario: API and database are up
- **WHEN** a caller (the MCP server, Docker, or a person with curl) sends `GET /api/health` and PostgreSQL is reachable
- **THEN** the response is 200 with body `{"status": "ok"}`

#### Scenario: Database is unreachable
- **WHEN** a caller sends `GET /api/health` and the database query fails
- **THEN** the response is 503 with body `{"detail": "Database unavailable"}`
- **AND** the error details are written to the log, not the response

### Requirement: Health route needs no authentication
`GET /api/health` SHALL be reachable without any credentials, and SHALL remain the only unauthenticated API route once service-token auth is added.

#### Scenario: Request without credentials
- **WHEN** a caller sends `GET /api/health` with no `Authorization` header
- **THEN** the response is 200 (with the database up), not 401

### Requirement: Stack starts with one command
Running `docker compose up` with a `.env` copied from `.env.example` SHALL start the `web` and `db` services. The `web` service SHALL wait for the database, apply migrations, and serve the API on `127.0.0.1:8000` only.

#### Scenario: Fresh start
- **WHEN** a developer copies `.env.example` to `.env`, sets `DJANGO_SECRET_KEY`, and runs `docker compose up`
- **THEN** `curl http://127.0.0.1:8000/api/health` returns 200 once both services are running

#### Scenario: Missing secret key
- **WHEN** `DJANGO_SECRET_KEY` is not set
- **THEN** the `web` service fails at startup with an error naming the missing key

