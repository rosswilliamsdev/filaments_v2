# Frontend Planning Doc: Filaments v2 Web UI
_Generated 2026-11-19_

## Project Context
A private web UI for Filaments v2, used by one person (Ross). Filaments are captured by dictating to Claude in the Claude app, which saves them through the MCP server; the web UI is where they are browsed, searched, and edited. Each filament has a title, a Markdown body, and tags.

- **Core job-to-be-done:** scan recent thinking, find a past filament quickly, and correct or refine it.
- **New project**, built alongside the Filaments v2 backend (see `PRD.md`).
- **No deadline.** The web UI ships in Phase 2, after voice capture works. It is reachable remotely (including from a phone) through the same Cloudflare Tunnel, behind Django login.

## Tech Stack
- **Rendering:** Django templates (server-rendered), with HTMX for partial swaps
- **Styling:** Tailwind CSS via the standalone CLI (no Node install)
- **Components:** Django `{% include %}` partials; each HTMX swap target is its own partial
- **JS:** HTMX only; no frontend framework
- **Markdown:** rendered server-side
- **Deployment:** served by Django from the home laptop (Docker Compose)

## Aesthetic Direction
The Filaments v1 design system carries over unchanged:
- **Palette:** warm neutrals
- **Mode:** light only
- **Typography:** Lora (headings/reading), Inter (UI), JetBrains Mono (code/metadata)
- **Shape:** 8px radius
- **Motion:** 150ms, minimal
- **Primary reference:** Day One (desktop app layout and journal feel)

Design tokens are defined in the Tailwind config so the whole UI draws from one source.

## Interaction Philosophy
- **Motion budget:** subtle polish only, at 150ms (fades on swaps, loading indicators)
- **Input:** mouse-driven; no keyboard shortcut layer in scope
- **HTMX hooks:** `.htmx-indicator` / `.htmx-request` for loading states; `.htmx-swapping` / `.htmx-added` for fades
- **No** drag-and-drop or gesture patterns

## UX Flows

### Primary Flow
1. Open the site and land on a **split pane**: the feed on the left, detail on the right.
2. The **feed** is chronological, newest first, with a **search box at the top**.
3. The feed **infinite-scrolls**: the last card uses `hx-trigger="revealed"` to load the next page of 20.
4. Typing in search updates the feed after a **300ms debounce**.
5. Clicking a filament loads it in the **detail pane**: title, body (Markdown), tags, and created/updated dates.
6. Clicking a tag filters the feed to that tag.
7. Fields in the detail pane are **editable in place** and **auto-save** (see Forms & Validation).

### Edge States
- **Empty feed:** a short prompt to dictate a first filament to Claude.
- **No search results:** "No filaments match", with a button to clear the search.
- **Loading (feed):** a small spinner at the bottom of the feed while the next page loads.
- **Loading (save):** a subtle "Saving… / Saved" indicator in the detail pane.
- **Save failure** (e.g. laptop unreachable): keep the edits on screen, show "Not saved, retrying", and retry automatically.
- **Dense:** handled by infinite scroll with 20 per page.

### Forms & Validation
- **Edit pattern:** in-place editing with auto-save; no Edit/Save buttons.
- **Debounce:** a save fires after about 1 second without typing.
- **Validation:** server-side, against the shared Pydantic schemas (tags ≤8, lowercase, hyphenated).

### URL State
- The selected filament and the active search live in the URL via `hx-push-url`, e.g. `/filaments/<id>?q=album`.
- Refresh, the back button, and bookmarks restore the same view.

## Responsive & Accessibility
- **Desktop-first.**
- **Small screens (Phase 2 phone access):** the split pane collapses to a **single column**. The feed shows first, and tapping a filament opens its detail.
- **Accessibility baseline:** semantic HTML, WCAG AA contrast, visible focus states, and 44px tap targets in the mobile layout.

## Performance & Quality Targets
- **Feed:** 20 filaments per page, loaded on scroll.
- **Search:** 300ms debounce.
- **Auto-save:** about 1 second debounce.
- **Priority areas:** form reliability (auto-save must never silently lose edits), then accessibility baseline, then mobile layout.

## Deferred Decisions
- Whether tags are editable in the web UI (title and body are), and the tag editing UI
- Whether the web UI can create new filaments (the data model's `source: "web"` allows it), or capture stays Claude-only
- Delete UX: confirmation step and access to soft-deleted filaments
- Save-failure retry limits and what happens after repeated failures
- Exact breakpoint for the single-column layout
- Tailwind wrapper: `pytailwindcss` or `django-tailwind-cli`

## References
- Vercel Web Interface Guidelines: https://vercel.com/design/guidelines
- Day One (primary design reference)
- `PRD.md` (Filaments v2)
