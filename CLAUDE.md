# CLAUDE.md

Guidance for Claude Code when working in this repository.

## Project status

Roadmap steps 1–4 are in place: Docker Compose scaffolding with `GET /api/health`, the `Filament`/`Tag` models, the shared `schemas` package, and create/get/update/delete under `/api/filaments`. List/search, API auth, the MCP server and OAuth come in later steps — check `roadmap.md` before assuming a module exists.

Source of truth, in priority order:
1. `docs/PRD.md` — scope, goals, non-goals, phasing
2. `docs/backend-planning-doc.md` — data model, API, auth, error handling
3. `docs/frontend-planning-doc.md` — Phase 2 web UI
4. `openspec/` — change proposals and specs (spec-driven workflow)

`roadmap.md` sets the build order. Each numbered step is meant to be one OpenSpec change; check it to see what comes next and what a step depends on.

## Layout

A uv workspace with one lockfile (`uv.lock`). Python 3.13.

```
pyproject.toml     # workspace root: dev deps, Ruff and pytest config
backend/           # filaments-backend: Django project (config/), Ninja API (api/), models + write logic (filaments/services.py), tests/
schemas/           # filaments-schemas: shared Pydantic models, import name `schemas`. No Django imports.
compose.yaml       # web (gunicorn) + db (postgres:17); both bound to 127.0.0.1 only
```

The MCP server will be added as `mcp_server/` (import `filaments_mcp`). Never name a local package `mcp` — it shadows the MCP SDK.

## Commands

Run from the repo root. Settings come from `.env` (copy `.env.example`; `DJANGO_SECRET_KEY` is required). Commands on the host need `--env-file .env`.

```bash
uv sync                                          # install everything (workspace + dev tools)
docker compose up -d --build                     # run web + db; API at http://127.0.0.1:8000/api/health
docker compose up -d db                          # db only, for local dev and tests
uv run --env-file .env backend/manage.py runserver   # dev server with autoreload (needs db up)
uv run --env-file .env backend/manage.py migrate
uv run --env-file .env pytest                    # tests run against the Compose Postgres (needs db up)
uv run ruff check . && uv run ruff format .      # lint + format
```

Logs: console always; in Compose also `logs/django.log` (gitignored).

If another Postgres already holds port 5432 on the host, set `POSTGRES_PORT` in `.env` to a free port (e.g. 5433); Compose publishes the db on that port and `web` still uses 5432 internally.

`FILAMENTS_TIMEZONE` (IANA name, e.g. `America/Chicago`; default `UTC`) sets Django's `TIME_ZONE`. Timestamps are stored in UTC; the home zone decides what a calendar day means for date filters. An unknown name stops startup.

`pytest` runs `backend/tests` (needs the db) and `schemas/tests` (no database).

If a request conflicts with these docs, point out the conflict before writing code. Each planning doc has a **Deferred Decisions** section — don't silently decide those; raise them.

## What Filaments v2 is

A single-user, private notes store filled by dictating to Claude in the Claude app. Claude turns speech into a note (title, Markdown body, tags) and saves it through a remote MCP server. The backend is just storage and search — **no server-side AI**.

```
Claude (dictation, phone) → custom connector, HTTPS + OAuth → Cloudflare Tunnel
  → MCP server (FastMCP, Streamable HTTP) → service token → Django Ninja API (localhost) → Postgres
```

## Stack (decided)

- Python only for backend and MCP server
- Django 5.2 LTS + Django Ninja, PostgreSQL with `django.contrib.postgres` full-text search
- MCP server: official MCP Python SDK (FastMCP), Streamable HTTP; stdio entry point for local dev only
- Auth: django-oauth-toolkit (Claude → MCP), service bearer token from `.env` (MCP → API), Django session login (web UI)
- Phase 2 UI: Django templates + HTMX + Tailwind (standalone CLI, no Node)
- Docker Compose services: `web`, `db`, `mcp`, `cloudflared`; runs on a home laptop (Ubuntu Server)
- Tests: pytest-django

## Hard rules (from the non-goals)

Do **not** add: embeddings/pgvector, auto-linking between notes, server-side LLM calls, transcription, Celery, Redis, S3, multi-user accounts, sharing, a frontend JS framework, Node tooling, or a rich-text editor. Suggest them only if asked.

## Domain rules

- **Filament:** UUID id, `title`, `body` (Markdown), `tags` (M2M), `source` (`"claude"` | `"web"`), `search_vector`, `created_at`, `updated_at`, `deleted_at`.
- **Tag:** unique `name`, lowercase, hyphenated. Normalize server-side on every write: trim → strip accents (Latin letters only) → lowercase → each run of non-letters/digits (spaces, punctuation, `_`) to one `-` → trim `-` → dedupe → get-or-create. Empty or >50-character tags are rejected, not fixed. Max 8 tags per filament, counted after dedupe. Rules live in `schemas/tags.py`.
- **Soft delete:** default manager excludes `deleted_at IS NOT NULL`. A management command (nightly cron) hard-deletes rows soft-deleted >30 days ago.
- **Search:** `search_vector` weights title A, body B, GIN index. Order by rank when `q` is present, else `created_at` desc. `tags` filter means *all* must match.
- Filament + tag writes happen in a single transaction.

## Architecture conventions

- **Build for voice mode later.** Capture uses dictation today because voice mode can't call custom connector tools yet (tested 2026-11-19). Design as if it will: tool descriptions and results should work when spoken (short, plain-language confirmations and errors), and nothing should require the user to see a screen to complete a capture or search.

- **Shared Pydantic schemas** live in one `schemas` package, imported by both Ninja endpoints and MCP tools. Never duplicate a request/response shape between the two.
- **The MCP server is a thin client** over the HTTP API. It never touches the database or Django ORM directly. Business logic belongs in Django.
- MCP tools map one-to-one onto API routes (see `docs/backend-planning-doc.md` → API Design).
- The API is never exposed through the tunnel. Only the MCP server and OAuth endpoints are public; `/api/health` is the one unauthenticated API route.
- Errors: Ninja default `{"detail": ...}`. 422s carry field-level detail so Claude can retry. The MCP layer translates API errors into readable messages (e.g. "Tag limit is 8; got 10"). 500s return a generic message; tracebacks go to the log only.

## Secrets

Secrets live in `.env` (gitignored). Any new key must also be added to `.env.example`. Never commit real tokens.

## Workflow

- This repo uses **OpenSpec** (`openspec/`, `/opsx:*` commands). For non-trivial features, propose a change (`/opsx:propose`) before implementing, then `/opsx:apply`.
- Prioritize tests for the API endpoints and search filters — those are what Claude relies on.
- Keep the Commands section above current when a step adds a service, env var or command.
