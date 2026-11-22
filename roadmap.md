# Filaments v2 — Development Roadmap

_Created 2026-11-19_

The order to build Filaments v2, one feature at a time. Each step is sized to be one OpenSpec change (`/opsx:propose` → `/opsx:apply` → `/opsx:archive`) and ends with something you can check works.

Scope and design decisions live in [`docs/PRD.md`](docs/PRD.md), [`docs/backend-planning-doc.md`](docs/backend-planning-doc.md), and [`docs/frontend-planning-doc.md`](docs/frontend-planning-doc.md). This file only covers **order** and **why that order**.

## Ordering principles

1. **Riskiest unknowns first.** The open risk that could still change the plan is the OAuth flow Claude expects (PRD risk #2), so it can start early, in parallel with the API. Risk #1 (voice mode) was settled by step 0.
2. **Build from the bottom up.** Models → shared schemas → API → MCP tools → public exposure. Each layer is tested before the next one depends on it.
3. **Stdio first, remote second.** Every MCP tool is checked locally over stdio before it goes behind the tunnel and OAuth.
4. **Data safety before real data.** Backups are running before notes you care about go in.

## At a glance

| # | Feature | Phase | Depends on |
|---|---------|-------|------------|
| 0 | ~~Voice-mode spike~~ ✅ done — use dictation | Phase 1 | — |
| 1 | Project scaffolding | Phase 1 | — |
| 2 | Data model | Phase 1 | 1 |
| 3 | Shared schemas + tag normalization | Phase 1 | 2 |
| 4 | API: create, get, update, delete | Phase 1 | 3 |
| 5 | API: list, search, tags | Phase 1 | 4 |
| 6 | Service-token auth on the API | Phase 1 | 4 |
| 7 | MCP server over stdio | Phase 1 | 5, 6 |
| 8 | OAuth authorization server | Phase 1 | 1 |
| 9 | Remote MCP: Streamable HTTP + tunnel | Phase 1 | 7, 8 |
| 10 | Backups + soft-delete sweep | Phase 1 | 2 |
| 11 | Phase 1 acceptance: dictation end to end | Phase 1 | 9, 10 |
| 12 | Web UI shell + login | Phase 2 | 11 |
| 13 | Feed: list, infinite scroll, search | Phase 2 | 12 |
| 14 | Detail pane + Markdown rendering | Phase 2 | 13 |
| 15 | In-place editing + auto-save | Phase 2 | 14 |
| 16 | Mobile layout + accessibility pass | Phase 2 | 15 |

Steps 8 and 10 don't depend on the API chain, so they can be done earlier or alongside steps 4–7.

---

## Phase 1 — Voice capture (MVP)

### 0. Voice-mode spike — ✅ done 2026-11-19
**Result:** Voice mode could not call custom connector tools. Dictation (speech-to-text into a normal Claude chat) can, so capture uses dictation for now. Nothing else in the plan changes: the MCP tools, OAuth, and tunnel work the same way.
**Going forward:** Build as if voice mode will work later. Step 7 makes tool responses readable aloud, and the Future list includes retesting voice mode.
**Mitigates:** PRD risk #1.

### 1. Project scaffolding
**Goal:** An empty Django project that runs in Docker Compose.
- Django 5.2 project, `pyproject.toml`, `.env` / `.env.example`, `.gitignore`
- Docker Compose with `web` and `db` (add `mcp` and `cloudflared` in later steps)
- pytest-django set up with one passing test; `GET /api/health` via Ninja
- Fill in the real commands in `CLAUDE.md` and remove the "Pre-code" note

**Done when:** `docker compose up` works and `/api/health` returns 200.

### 2. Data model
**Goal:** `Filament` and `Tag` in Postgres.
- `Filament` (UUID, title, body, source, timestamps, `deleted_at`) and `Tag` (unique name), M2M
- `search_vector` with a GIN index (title weight A, body weight B)
- Default manager that hides soft-deleted rows
- **Settled:** `search_vector` is a `GeneratedField` (`english` config); tags stay out of it and are matched in step 5

**Done when:** Migrations apply, and model tests cover the soft-delete manager and the search vector updating.

### 3. Shared schemas + tag normalization
**Goal:** One place that defines every request and response shape.
- `schemas` package: create/update/read filament, tag-with-count, list/search params
- Tag normalization (trim → strip accents → lowercase → non-letters/digits to hyphens → dedupe) and the 8-tag limit, as validators
- Home timezone (`FILAMENTS_TIMEZONE`) so date filters mean the user's local day
- No Django imports in `schemas`, so the MCP server can install it on its own

**Done when:** Unit tests cover normalization, the tag limit, and invalid input.

### 4. API: create, get, update, delete
**Goal:** Write and read single filaments.
- `POST`, `GET /{id}`, `PATCH /{id}`, `DELETE /{id}` (soft delete)
- Filament + tag writes in one transaction; tags get-or-created after normalization
- `{"detail": ...}` errors; 422s with field-level detail

**Done when:** Integration tests cover each route, including 404 on a soft-deleted filament and 422 on 9+ tags.

### 5. API: list, search, tags
**Goal:** The retrieval Claude depends on.
- `GET /api/filaments` with `q`, `tags` (all must match), `date_from`, `date_to`, `limit`, `offset`
- Ordered by rank when `q` is set, otherwise newest first
- `q` matches the search vector **or** tag names (agreed in step 2; tags aren't in the generated vector), using the `english` config
- `GET /api/tags` with usage counts (excluding soft-deleted filaments); tags with no remaining filaments are kept in the table but hidden here

**Done when:** Tests cover each filter alone and combined, ranking order, and paging.

### 6. Service-token auth on the API
**Goal:** Only the MCP server (and later the web UI) can call the API.
- A custom Ninja auth class that checks a bearer token from `.env`
- Every route except `/api/health` requires it

**Done when:** Tests confirm 401 without the token and 200 with it.

### 7. MCP server over stdio
**Goal:** All seven tools working locally against the real API.
- FastMCP server in its own `mcp` service, an HTTP client to the API using the service token
- Tools: `create_filament`, `search_filaments`, `list_filaments`, `get_filament`, `update_filament`, `delete_filament`, `list_tags`
- Tool inputs use the shared schemas; API errors become readable messages
- Voice-ready responses: short, plain-language confirmations and errors that make sense read aloud (e.g. "Saved 'Album cover ideas' with tags music, design")
- **Deferred decision to settle here:** keep `list_filaments` and `search_filaments` separate or merge them

**Done when:** A local Claude client (e.g. Claude Code or Claude Desktop over stdio) can create, find, edit, and delete a filament.

### 8. OAuth authorization server
**Goal:** The OAuth flow claude.ai custom connectors expect.
- django-oauth-toolkit with whatever Claude needs (check: dynamic client registration, PKCE, metadata endpoints, token lifetimes)
- Login with your Django account during connector setup
- **Deferred decisions to settle here:** the exact OAuth details, and whether the MCP server checks tokens by introspection against Django or as self-contained JWTs (never by reading the database)

**Done when:** You can complete the OAuth flow by hand (or with a test client) and receive a token the MCP server would accept.
**Resolves:** PRD risk #2.

### 9. Remote MCP: Streamable HTTP + tunnel
**Goal:** The MCP server reachable from claude.ai, protected by OAuth.
- Streamable HTTP transport alongside the stdio entry point
- MCP server checks the OAuth token on every request
- `cloudflared` service in Docker Compose; only the MCP and OAuth endpoints are routed, never `/api/`
- **Deferred decision to settle here:** the domain for the tunnel hostname

**Done when:** The connector is added in claude.ai on desktop, and a request without a token is rejected.

### 10. Backups + soft-delete sweep
**Goal:** Data survives the laptop failing.
- Nightly `pg_dump` to a destination off the laptop, by system cron
- Management command that hard-deletes filaments soft-deleted more than 30 days ago, by nightly cron
- **Deferred decision to settle here:** the backup destination
- **Test a restore** into a fresh database

**Done when:** A backup from last night restores successfully, and the sweep has a test.
**Resolves:** PRD risk #3.

### 11. Phase 1 acceptance: dictation end to end
**Goal:** The MVP works the way it's meant to be used.
- From the phone, dictating into a Claude chat: capture a note, find it by keyword, find it by tag, edit it, delete it
- Laptop set up for always-on (lid closed, no sleep, Docker on boot)

**Done when:** A week of real daily use with no lost notes.

---

## Phase 2 — Web UI

### 12. Web UI shell + login
- Django session login, base template, Tailwind standalone CLI with the v1 design tokens (warm neutrals, Lora/Inter/JetBrains Mono, 8px radius)
- HTMX loaded; split-pane layout skeleton
- Route the web UI through the tunnel behind login
- **Deferred decision to settle here:** `pytailwindcss` vs. `django-tailwind-cli`

### 13. Feed: list, infinite scroll, search
- Newest first, 20 per page, the next page loads when the last card scrolls into view (`hx-trigger="revealed"`)
- Search box with a 300ms debounce; clicking a tag filters the feed
- Search and filters kept in the URL with `hx-push-url`
- Empty-feed and no-results states

### 14. Detail pane + Markdown rendering
- Title, Markdown body rendered on the server, tags, created/updated dates
- Selected filament kept in the URL (`/filaments/<id>?q=...`), so refresh, back, and bookmarks restore the view

### 15. In-place editing + auto-save
- Editable title and body, saved after about 1 second without typing; "Saving… / Saved" indicator
- On failure: edits stay on screen, "Not saved, retrying", automatic retry
- **Deferred decisions to settle here:** whether tags are editable, retry limits, delete UX, and whether the web UI can create filaments

**Done when:** Tests show that a failed save never silently loses edits.

### 16. Mobile layout + accessibility pass
- Single column on small screens; feed first, tap to open detail
- WCAG AA contrast, visible focus states, 44px tap targets
- Review against the Vercel Web Interface Guidelines (`/web-interface-guidelines`)
- **Deferred decision to settle here:** the single-column breakpoint

---

## Future (not scheduled)

- Voice mode capture: retest from time to time; once it can call custom connector tools, run the step 11 checks in voice mode

- iOS Share Extension
- Export all filaments to Markdown
- Move from the laptop to Railway or a VPS
- Attachments (PRD open question #6)
