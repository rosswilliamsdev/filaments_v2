# Filaments v2 — Project Requirements Document

> **Type:** Personal
> **Status:** Draft
> **Last Updated:** 2026-11-19
> **Supersedes:** Filaments v1 plan (iOS app + server-side AI pipeline)

---

## Problem Statement

Thoughts come up throughout the day, and capturing them is slow (typing) or scattered across apps. Filaments v2 is a private notes repository I fill by dictating to Claude in the Claude app (speech-to-text into a normal chat). Claude turns what I say into a clean note with a title and tags and saves it through a Python MCP server. Later, Claude finds notes again by searching tags and keywords, and I can browse and edit them in a private web UI.

Filaments v1 planned a custom iOS app and an in-house AI pipeline. In v2, Claude handles capture and organization, so the backend is just storage and search.

---

## Goals & Non-Goals

### Goals
- Speak a note to Claude and have it saved, with a title and tags, in one step
- Ask Claude to find past notes; Claude searches by tags and keywords and answers from the results
- Own the data: single user, my Postgres database, my hardware
- Private web UI to browse, search, and edit notes
- Python-only backend and MCP server

### Non-Goals
- No multi-user accounts, sharing, or publishing
- No Siri capture, ever
- No native iOS app in v2
- No embeddings, vector search, or automatic linking between notes — Claude's tags and keyword search cover retrieval
- No in-house transcription or AI processing — Claude does this before calling the tools
- No Celery, Redis, or S3
- [TBD] File/image/audio attachments

---

## Feature List & Scope

### In Scope
- **Capture via Claude:** Claude cleans up the spoken text, writes a title, picks tags (reusing existing ones via `list_tags`), and calls `create_filament`
- **Tags:** lowercase, hyphenated, ≤8 per filament
- **Search:** Postgres full-text search on title and body (English stemming), where keywords also match tag names; filterable by tags and date range
- **MCP tools:**
  - `create_filament(title, body, tags)`
  - `search_filaments(query?, tags?, date_from?, date_to?, limit?)`
  - `get_filament(id)`
  - `list_filaments(tag?, limit?, offset?)` — newest first
  - `update_filament(id, title?, body?, tags?)`
  - `delete_filament(id)` — soft delete
  - `list_tags()` — all tags with usage counts
- **Web UI:** see `frontend-planning-doc.md`
- **Backups:** automated nightly `pg_dump` to a location off the laptop

### Out of Scope
- An "Ask AI" endpoint with server-side LLM calls — Claude answers questions by calling the tools
- Collaboration, comments, sharing links
- Rich-text editor (Markdown only)

---

## v1 Scope / Phasing

### Phase 1 (MVP) — Voice Capture, Remote from Day One
Dictation happens on the phone and custom connectors are remote MCP servers, so remote access is part of the MVP.
- Django + Postgres on the home laptop via Docker Compose
- Django Ninja API
- Python MCP server over Streamable HTTP, exposed over HTTPS through Cloudflare Tunnel
- OAuth (django-oauth-toolkit) so the server can be added as a custom connector in claude.ai and used from the Claude app on the phone
- All MCP tools above
- A stdio entry point for the same MCP server, used only as a local dev harness
- Nightly backups

### Phase 2 — Web UI
- Web UI with Django templates, HTMX, and Tailwind (see `frontend-planning-doc.md`), behind Django login

### Future Phases
- Voice mode capture, once it supports custom connector tools (no backend changes expected)
- iOS Share Extension
- Export all filaments to Markdown
- Move from laptop to Railway or a VPS if needed

---

## Tech Stack & Architecture Notes

| Layer       | Technology |
|-------------|------------|
| Frontend    | Django templates + HTMX, Tailwind CSS (standalone CLI), Markdown rendering — see `frontend-planning-doc.md` |
| Backend     | Django 5.2 LTS + Django Ninja (Pydantic schemas, auto OpenAPI docs) |
| Database    | PostgreSQL with built-in full-text search |
| MCP server  | Python, official MCP SDK (FastMCP) |
| Auth        | OAuth via django-oauth-toolkit (Claude → MCP server); service bearer token (MCP server → API); Django session login (web UI) |
| Hosting     | Old laptop as home server, Ubuntu Server (headless), exposed via Cloudflare Tunnel |
| Other       | Docker Compose, Git |

**Architecture (Phase 1):**

```
You ──dictate──> Claude app chat (phone)
                 │  Claude writes title, body, tags
                 └─ custom connector ── HTTPS + OAuth ──> Cloudflare Tunnel
                                                            └─ MCP server (Streamable HTTP, laptop)
                                                                 └─ service token ──> Django Ninja API (laptop, localhost)
                                                                                        └─ PostgreSQL
```

See `backend-planning-doc.md` for the full backend design.

**Data model:**
- `Filament`: id (UUID), title, body (Markdown), tags (M2M → Tag), source (`"claude"`, `"web"`), search_vector (generated column, `english` config), created_at, updated_at, deleted_at (soft-delete tombstone)
- `Tag`: id, name (unique, lowercase, hyphenated)

**Dropped from v1:** React Native/Expo app, Whisper transcription, server-side Claude extraction (summary, key ideas, action items), embeddings and pgvector, auto-linking and `FilamentLink`, Celery + Redis, S3, the `/process` endpoint and `pipeline_attempts` recovery, Sign in with Google.

**Notes:**
- The MCP server is a thin client over the API, so the same API serves both the web UI and Claude.
- Request and response schemas are shared Pydantic models (e.g. a `schemas` package). The Ninja endpoints and the MCP tools both import them, so Claude's tool inputs and the API validate against the same definition.
- Why Ninja over DRF: the API is small and single-client, Pydantic schemas are shared with the MCP SDK, and function-based endpoints mean less boilerplate. Trade-off accepted: smaller ecosystem than DRF and no browsable API (Swagger docs instead).
- The 30-day soft-delete sweep runs as a Django management command on a system cron job on the laptop.
- The laptop runs lid-closed, never sleeps, and stays plugged in so the battery covers short outages.

---

## Constraints

- **Timeline:** No fixed deadline
- **Team:** Solo
- **Budget / Infra:** Minimal — existing laptop, free Cloudflare Tunnel; a domain may be needed for the tunnel hostname
- **Other:** Python-only backend and MCP server

---

## Open Questions & Risks

| # | Question / Risk | Status |
|---|-----------------|--------|
| 1 | Voice mode could not call custom connector tools when tested (2026-11-19). Capture uses dictation (speech-to-text in a normal Claude chat) for now. Build as if voice mode will work later: tool responses must make sense read aloud. Retest voice mode periodically | Mitigated |
| 2 | OAuth is the most complex piece and is now in the MVP. Exact flow Claude's custom connectors expect (e.g. dynamic client registration) to be confirmed during build | Open |
| 3 | Single laptop = single point of failure; choose a backup destination and test a restore | Open |
| 4 | Capture only works while the laptop is on and online | Accepted |
| 5 | Tag drift (near-duplicate tags) weakens search; mitigated by `list_tags` | Mitigated |
| 6 | Attachments (images, audio) in or out of scope | Open |
