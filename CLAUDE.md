# CLAUDE.md

Guidance for Claude Code when working in this repository.

## Project status

Roadmap steps 1–9 are in place: Docker Compose scaffolding with `GET /api/health`, the `Filament`/`Tag` models, the shared `schemas` package, create/get/update/delete plus list/search under `/api/filaments`, and `/api/tags`, all behind a service bearer token, the stdio MCP server with six tools, the OAuth authorization server (django-oauth-toolkit) with its login page, and remote access: MCP over Streamable HTTP with OAuth introspection, a Caddy edge allowlist and a Cloudflare Tunnel at `https://myfilaments.dev` (setup: `docs/remote-access.md`). Backups and the soft-delete sweep come in step 10 — check `roadmap.md` before assuming a module exists.

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
backend/           # filaments-backend: Django project (config/), Ninja API (api/), models + write logic (filaments/services.py) + read/search logic (filaments/queries.py), OAuth clients + login lockout (accounts/), tests/
schemas/           # filaments-schemas: shared Pydantic models, import name `schemas`. No Django imports.
mcp_server/        # filaments-mcp: FastMCP server, import `filaments_mcp`. HTTP client to the API; no Django.
edge/Caddyfile     # the public allowlist: what the tunnel can reach (everything else 404)
compose.yaml       # db + web by default; profile `remote` adds mcp + edge (127.0.0.1:8080); `public` adds cloudflared
```

Never name a local package `mcp` — it shadows the MCP SDK.

## Commands

Run from the repo root. Settings come from `.env` (copy `.env.example`; `DJANGO_SECRET_KEY` is required). Commands on the host need `--env-file .env`.

```bash
uv sync                                          # install everything (workspace + dev tools)
docker compose up -d --build                     # run web + db; API at http://127.0.0.1:8000/api/health
docker compose up -d db                          # db only, for local dev and tests
docker compose --profile remote up -d --build    # + mcp and edge: test the public surface at http://127.0.0.1:8080
docker compose --profile public up -d --build    # + cloudflared: the laptop, online at https://myfilaments.dev
uv run --env-file .env backend/manage.py runserver   # dev server with autoreload (needs db up)
uv run --env-file .env backend/manage.py migrate
uv run --env-file .env pytest                    # tests run against the Compose Postgres (needs db up)
docker compose exec web python manage.py createsuperuser      # your account (OAuth sign-in, admin)
docker compose exec web python manage.py setup_oauth_clients  # Claude + MCP clients; prints secrets once (--rotate for new)
uv run ruff check . && uv run ruff format .      # lint + format
uv run --env-file .env python -m filaments_mcp   # MCP server over stdio (needs the API up); normally launched by a client
claude mcp add filaments -- uv run --directory "$PWD" --env-file "$PWD/.env" python -m filaments_mcp   # register with Claude Code
```

Logs: console always; in Compose also `logs/django.log` (gitignored).

If another Postgres already holds port 5432 on the host, set `POSTGRES_PORT` in `.env` to a free port (e.g. 5433); Compose publishes the db on that port and `web` still uses 5432 internally.

`FILAMENTS_TIMEZONE` (IANA name, e.g. `America/Chicago`; default `UTC`) sets Django's `TIME_ZONE`. Timestamps are stored in UTC; the home zone decides what a calendar day means for date filters. An unknown name stops startup.

`FILAMENTS_API_TOKEN` (required, 32+ characters) is the bearer token for every API route except `/api/health`; generate it with `uv run python -c "import secrets; print(secrets.token_urlsafe(32))"`. `FILAMENTS_PUBLIC_URL` (default `http://127.0.0.1:8000`) is the OAuth issuer: the public base URL Claude signs in to (the tunnel URL in step 9). OAuth endpoints: `/.well-known/oauth-authorization-server`, `/o/{authorize,token,revoke_token,introspect}/`, login at `/accounts/login/`. OAuth tokens never work on `/api/`.

**Remote access** (`docs/remote-access.md`): `python -m filaments_mcp --http` needs `FILAMENTS_PUBLIC_URL` (`https://`; plain http only with `FILAMENTS_ALLOW_INSECURE_PUBLIC_URL=true`, never on the laptop) and `FILAMENTS_INTROSPECTION_CLIENT_ID`/`_SECRET` (`FILAMENTS_INTROSPECTION_URL` defaults to `http://web:8000/o/introspect/`). Every MCP request is checked by introspection (scope `notes`, `aud` = `<public>/mcp`, no cache). `edge/Caddyfile` is the firewall: changing it changes what the internet can reach, so curl-test blocked paths (`/api/`, `/admin/`, `/o/introspect/` → 404) after any edit. The tunnel token is `CLOUDFLARE_TUNNEL_TOKEN`.

`/api/docs` and `/api/openapi.json` exist only when `DJANGO_DEBUG` is on. Tests use a fixed token from `backend/tests/conftest.py`, whose `client` fixture sends it (`anon_client` doesn't).

The MCP server reads `FILAMENTS_API_TOKEN` and `FILAMENTS_API_URL` (default `http://127.0.0.1:8000/api`). It speaks stdio, so stdout is the protocol: log to stderr only, never `print()`.

`pytest` runs `backend/tests` (needs the db; includes an MCP end-to-end test against `live_server`), `mcp_server/tests` and `schemas/tests` (no database).

If a request conflicts with these docs, point out the conflict before writing code. Each planning doc has a **Deferred Decisions** section — don't silently decide those; raise them.

## What Filaments v2 is

A single-user, private notes store filled by dictating to Claude in the Claude app. Claude turns speech into a note (title, Markdown body, tags) and saves it through a remote MCP server. The backend is just storage and search — **no server-side AI**.

```
Claude (dictation, phone) → custom connector, HTTPS + OAuth → Cloudflare Tunnel
  → MCP server (FastMCP 4, Streamable HTTP) → service token → Django Ninja API (localhost) → Postgres
```

## Stack (decided)

- Python only for backend and MCP server
- Django 5.2 LTS + Django Ninja, PostgreSQL with `django.contrib.postgres` full-text search
- MCP server: FastMCP 4 (gofastmcp.com), built on the official MCP SDK (`fastmcp>=4.2,<5`; the official SDK's own copy is now called `MCPServer`), Streamable HTTP; stdio entry point for local dev only
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
- **Search:** `search_vector` weights title A, body B, GIN index. Keyword search (`q`, websearch syntax) appends tag names to that vector at query time (`filaments/queries.py`), so it does not use the GIN index. Order by rank when `q` is present, else `created_at` desc. `tags` filter means *all* must match.
- Filament + tag writes happen in a single transaction.

## Architecture conventions

- **Build for voice mode later.** Capture uses dictation today because voice mode can't call custom connector tools yet (tested 2026-11-19). Design as if it will: tool descriptions and results should work when spoken (short, plain-language confirmations and errors), and nothing should require the user to see a screen to complete a capture or search.

- **Shared Pydantic schemas** live in one `schemas` package, imported by both Ninja endpoints and MCP tools. Never duplicate a request/response shape between the two. MCP tool parameters are plain types (so FastMCP's own validation can't produce unspeakable errors) with descriptions read from the shared models; each tool validates by building the shared model.
- **The MCP server is a thin client** over the HTTP API. It never touches the database or Django ORM directly. Business logic belongs in Django.
- MCP tools map one-to-one onto API routes (see `docs/backend-planning-doc.md` → API Design).
- The API is never exposed through the tunnel. Only the MCP server and OAuth endpoints are public; `/api/health` is the one unauthenticated API route.
- Errors: Ninja default `{"detail": ...}`. 422s carry field-level detail so Claude can retry. The MCP layer translates API errors into readable messages (e.g. "Tag limit is 8; got 10"). 500s return a generic message; tracebacks go to the log only.

## Secrets

Secrets live in `.env` (gitignored). Any new key must also be added to `.env.example`. Never commit real tokens.

## Workflow

- This repo uses **OpenSpec** (`openspec/`, `/opsx:*` commands). For non-trivial features, propose a change (`/opsx:propose`) before implementing, then `/opsx:apply`.
- **After finishing `/opsx:apply`, run one round of `/code-review`** on the change. Verify each finding (reproduce it where possible), implement the fixes for the real ones with tests, and update the change's spec/design if a fix changes behavior. Report findings that turned out to be false alarms rather than silently dropping them. One round only — don't re-review the fixes unless asked. Then wait for "commit and push" before archiving.
- Prioritize tests for the API endpoints and search filters — those are what Claude relies on.
- Keep the Commands section above current when a step adds a service, env var or command.
