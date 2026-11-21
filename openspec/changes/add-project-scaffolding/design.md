## Context

The repo has planning docs only. The stack is fixed by `PRD.md` and `backend-planning-doc.md`: Django 5.2 LTS + Django Ninja, PostgreSQL, pytest-django, Docker Compose on an Ubuntu laptop. Development happens on a Mac. The docs do **not** fix the package layout, dependency manager, Python version, linter, or how settings differ between development and the laptop. Later steps depend on all of these, so this change decides them.

The layout has one hard constraint: roadmap step 3 says the `schemas` package has no Django imports, so the MCP server (step 7) can install it on its own. That means at least three installable packages sharing one repo:

```
            ┌───────────────┐
            │   schemas     │  Pydantic only, no Django
            └──────┬────────┘
          imports  │  imports
       ┌───────────┴───────────┐
┌──────▼────────┐      ┌───────▼────────┐
│   backend     │      │  mcp_server    │  (step 7)
│ Django+Ninja  │◀─HTTP┤  FastMCP       │
└───────────────┘      └────────────────┘
```

## Goals / Non-Goals

**Goals:**
- `docker compose up` starts `web` and `db`, and `GET /api/health` returns 200.
- A layout where `schemas` installs without Django, ready for steps 3 and 7.
- One lockfile and one command set for install, run, test and lint.
- The same settings module works on the Mac and on the laptop, controlled by `.env`.

**Non-Goals:**
- Models, migrations beyond Django's built-ins, real schemas (steps 2–3).
- Service-token auth (step 6), the MCP server (step 7), OAuth (step 8), `cloudflared` (step 9).
- CI, deployment automation, backups.

## Decisions

### 1. uv workspace with one lockfile

The root `pyproject.toml` is a virtual uv workspace (no package of its own) that holds dev tools (pytest, pytest-django, Ruff). Each package is a workspace member with its own `pyproject.toml`:

```
filaments_v2/
├── pyproject.toml          # workspace root, dev deps, ruff + pytest config
├── uv.lock
├── compose.yaml
├── .env.example
├── backend/                # member: filaments-backend
│   ├── pyproject.toml      # django, django-ninja, psycopg, gunicorn, filaments-schemas
│   ├── Dockerfile
│   ├── manage.py
│   ├── config/             # settings.py, urls.py, asgi.py, wsgi.py
│   ├── api/                # NinjaAPI instance + routers (health now)
│   └── tests/
└── schemas/                # member: filaments-schemas (import name: schemas)
    ├── pyproject.toml      # pydantic only
    └── src/schemas/__init__.py
```

The MCP server joins in step 7 as `mcp_server/` (distribution `filaments-mcp`, import `filaments_mcp`). It must **not** be importable as `mcp`, because that would shadow the MCP SDK.

**Why:** uv workspaces give one lockfile and resolved versions across packages, and each Docker image installs only its member (`uv sync --package filaments-backend`). The `schemas` boundary is real from day one: `backend` depends on it the same way `mcp_server` will.

**Alternatives:** a single package containing everything (simpler now, but `schemas` can't be installed without Django; step 7 would have to restructure). Poetry or pip-tools (they work, but uv is faster and has native workspaces). Separate repos (too heavy for a solo project).

**Stub `schemas` now:** an empty package costs nothing. It proves that installing a workspace member works in Docker before step 3 relies on it.

### 2. Python 3.13

Supported by Django 5.2 and current wheels for psycopg and pydantic. Pinned in `.python-version` and the Docker base image (`python:3.13-slim`).

### 3. One settings module driven by environment variables

`config/settings.py` reads everything from the environment, without django-environ, using a few small helpers for booleans and comma-separated lists:

| Key | Dev (Mac) | Laptop |
|---|---|---|
| `DJANGO_SECRET_KEY` | any string | real secret |
| `DJANGO_DEBUG` | `true` | `false` |
| `DJANGO_ALLOWED_HOSTS` | `localhost,127.0.0.1` | adds `web` and, in step 9, the tunnel hostname |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | empty | set in step 9 |
| `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`, `POSTGRES_PORT` | `POSTGRES_HOST=localhost` | `POSTGRES_HOST=db` |

Settings fail fast if `DJANGO_SECRET_KEY` is missing. `USE_TZ = True` and `TIME_ZONE = "UTC"`: timestamps are stored in UTC. The question of which timezone date filters use belongs to step 5.

**Alternatives:** split `settings/dev.py` and `settings/prod.py` modules (more files for a two-environment project, and they drift apart). django-environ (one more dependency for something a dozen lines handle).

### 4. Compose: `web` runs gunicorn, development runs `runserver`

- `db`: `postgres:17`, named volume, `pg_isready` healthcheck, port published on `127.0.0.1:5432` only, so tests and `runserver` on the Mac can reach it.
- `web`: built from `backend/Dockerfile`. It runs `migrate`, then `gunicorn config.wsgi`, waits for `db` to be healthy, and publishes `127.0.0.1:8000` only. The API is never exposed beyond localhost and the Docker network.
- Day-to-day development: `docker compose up db` plus `uv run backend/manage.py runserver` on the Mac for autoreload.

**Why gunicorn in Compose:** the Compose file is what runs on the laptop, and `runserver` is not meant for that. WSGI is enough. The MCP server is a separate process, so Django doesn't need ASGI.

### 5. Health route checks the database

`GET /api/health` runs `SELECT 1`. It returns `200 {"status": "ok"}` when that succeeds and `503 {"detail": "Database unavailable"}` when it fails. It is unauthenticated (the one public API route per `backend-planning-doc.md`) and registered on the project's single `NinjaAPI` instance at `/api/`. Ninja's docs stay at `/api/docs`. That's acceptable because `/api/` is never routed through the tunnel.

**Why check the database:** a 200 from a process that can't reach Postgres would hide the most likely failure on the laptop. The Compose healthcheck for `web` can use the same route.

### 6. Tests run on the Mac against the Compose database

pytest-django runs against PostgreSQL, not SQLite, because full-text search (step 5) is Postgres-only. Config lives in the root `pyproject.toml` (`DJANGO_SETTINGS_MODULE = "config.settings"`, `pythonpath = ["backend"]`). Command: `uv run pytest`.

### 7. Ruff for lint and format

Configured in the root `pyproject.toml`, with rules `E`, `F`, `I`, `UP`, `B`, `DJ`. Commands: `uv run ruff check .` and `uv run ruff format .`.

## Risks / Trade-offs

- **uv workspace in Docker:** the build context must include the root `pyproject.toml`, `uv.lock` and `schemas/`, not just `backend/`. → Build with context `.` and `dockerfile: backend/Dockerfile`.
- **`migrate` on every container start** could race if `web` ever runs several replicas. → It's one container, single user. Revisit only if that changes.
- **Tests need the `db` container running.** → Documented in `CLAUDE.md`. pytest fails with a clear connection error if it isn't running.
- **No auth on `/api/` until step 6.** → Nothing is reachable outside localhost until step 9.

## Migration Plan

None. This is the first code in the repo.

## Open Questions

- None blocking. The choices above (uv, Python 3.13, one settings module, Ruff, `postgres:17`) aren't covered by the planning docs. Change them here before running apply if you prefer something else.
