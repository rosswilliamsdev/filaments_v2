# Filaments v2

A private notes repository you fill by talking to Claude.

Dictate a thought to Claude in the Claude app. Claude cleans it up, writes a title, picks tags, and saves it through a self-hosted MCP server. Later, ask Claude to find past notes, or browse and edit them in a private web UI.

> **Status:** Phase 1 in progress. Scaffolding is done (Django + Postgres in Docker Compose, `GET /api/health`); see [`roadmap.md`](roadmap.md) for what's next.

## How it works

```
You ──dictate──> Claude app chat (phone)
                 │  Claude writes title, body, tags
                 └─ custom connector ── HTTPS + OAuth ──> Cloudflare Tunnel
                                                            └─ MCP server (Streamable HTTP)
                                                                 └─ service token ──> Django Ninja API (localhost)
                                                                                        └─ PostgreSQL
```

Claude does the thinking (transcription, cleanup, titling, tagging). The backend only stores and searches. Everything runs on hardware I own.

## Features

**Phase 1 — Voice capture (MVP)**
- MCP tools: `create_filament`, `search_filaments`, `get_filament`, `update_filament`, `delete_filament`, `list_tags`
- Postgres full-text search over title and body, filterable by tags and date range
- Tags normalized to lowercase-hyphenated, up to 8 per note; `list_tags` helps Claude reuse existing tags
- Soft delete with a 30-day purge
- OAuth so the server works as a claude.ai custom connector from a phone
- Nightly `pg_dump` backups off the machine

**Phase 2 — Web UI**
- Split-pane feed and detail view, infinite scroll, debounced search
- In-place editing with auto-save
- Django templates + HTMX + Tailwind, behind Django login

**Not planned:** multi-user, sharing, embeddings/vector search, server-side AI, native iOS app.

## Tech stack

| Layer      | Technology |
|------------|------------|
| Backend    | Django 5.2 LTS, Django Ninja |
| Database   | PostgreSQL (built-in full-text search) |
| MCP server | FastMCP 4 (built on the official MCP SDK), Streamable HTTP |
| Auth       | django-oauth-toolkit, service bearer token, Django sessions |
| Frontend   | Django templates, HTMX, Tailwind CSS (standalone CLI) |
| Hosting    | Home laptop (Ubuntu Server), Docker Compose, Cloudflare Tunnel |
| Testing    | pytest-django |

## Documentation

- [`docs/PRD.md`](docs/PRD.md) — goals, scope, phasing, open questions
- [`docs/backend-planning-doc.md`](docs/backend-planning-doc.md) — data model, API, auth, error handling
- [`docs/frontend-planning-doc.md`](docs/frontend-planning-doc.md) — web UI design and UX flows
- [`roadmap.md`](roadmap.md) — build order, feature by feature
- [`openspec/`](openspec/) — spec-driven change proposals

## Getting started

Requires [uv](https://docs.astral.sh/uv/) and Docker.

1. Copy `.env.example` to `.env`. Set `DJANGO_SECRET_KEY` and `POSTGRES_PASSWORD`.
2. `uv sync`
3. `docker compose up -d --build` (services so far: `web`, `db`)
4. `curl http://127.0.0.1:8000/api/health` should return `{"status": "ok"}`

Tests: `uv run --env-file .env pytest` (with the `db` container running). More commands are in [`CLAUDE.md`](CLAUDE.md).

Later steps add the `mcp` and `cloudflared` services; then you add the MCP server's public URL as a custom connector in claude.ai.

## License

Personal project — not licensed for reuse.
