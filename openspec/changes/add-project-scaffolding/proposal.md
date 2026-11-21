## Why

The repo holds planning docs only. Every later roadmap step (data model, schemas, API, MCP server, OAuth) needs a running Django project, a database, a test runner and a fixed code layout to build on. This is roadmap step 1, **Phase 1 (voice capture, MVP)**. It also fixes the package layout early, because the shared `schemas` package must be installable without Django and that is hard to change once steps 3–7 depend on it.

## What Changes

- Add a Python workspace at the repo root (one lockfile) with the Django project as a member and an empty, Django-free `schemas` package reserved for step 3.
- Add a Django 5.2 LTS project configured from environment variables, with settings that work for both local development and the laptop deployment.
- Add Django Ninja with a single unauthenticated route, `GET /api/health`, returning 200.
- Add Docker Compose with the `web` and `db` (PostgreSQL) services. The `mcp` and `cloudflared` services come in later steps.
- Add `.env.example` listing every required key. `.env` is already gitignored.
- Add pytest-django with a passing test for the health route.
- Add Ruff for linting and formatting.
- Update `CLAUDE.md` with the real setup, run, test and lint commands, and remove the "Pre-code" note. Update the README "Getting started" section to match.

## Capabilities

### New Capabilities
- `api-health`: an unauthenticated health route the MCP server, Docker and humans can use to check that the API is up.

### Modified Capabilities
_None. No specs exist yet._

## Impact

- **New code:** workspace `pyproject.toml` and `uv.lock`, the Django project under `backend/`, a stub `schemas/` package, `Dockerfile`, `compose.yaml`, test and lint config.
- **Dependencies:** Django 5.2, django-ninja, psycopg 3, pytest, pytest-django, Ruff. Managed with uv.
- **Docs:** `CLAUDE.md` and `README.md` get real commands.
- **Conflicts with planning docs:** none. The planning docs don't name a dependency manager, Python version, linter or package layout; this change decides them (see `design.md`).
- **Deferred decisions touched:** none. `GeneratedField` vs. update on save is step 2. The Tailwind wrapper is step 12.

## Open Questions

- The service-token auth for `/api/` arrives in step 6. Until then, the routes added in steps 4–5 have no auth. That is fine locally, because nothing is exposed through a tunnel before step 9.
