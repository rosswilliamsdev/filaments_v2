## Why

Finding notes again is half of what Claude does with Filaments ("what did I note about album covers last week?"). Steps 2–4 stored filaments and defined the list parameters; this change adds the retrieval routes Claude depends on, plus the tag list Claude uses to reuse existing tags. Phase: **Phase 1 (voice capture)**, roadmap step 5.

## What Changes

- Add `GET /api/filaments` taking `FilamentListParams` as query parameters and returning `FilamentList` (`items`, `total`, `limit`, `offset`):
  - `q`: parsed with Postgres `websearch_to_tsquery('english', …)` (words ANDed; supports `"quoted phrases"`, `-exclude`, `or`; never a syntax error). Matched against the stored title/body vector **combined with** the filament's tag names (tag words weighted A, like the title), so "music ideas" finds a note tagged `music` whose body says "ideas".
  - `tags`: every listed tag must be present; unknown tags give zero results.
  - `date_from` / `date_to`: inclusive calendar days on `created_at`, in the home timezone (`FILAMENTS_TIMEZONE`).
  - Order: rank (when `q` is set), then `created_at` newest first, then `id` for stable paging.
  - Full bodies in results; excerpts are revisited in step 7.
- Add `GET /api/tags` returning `TagWithCount` for every tag used by at least one non-deleted filament, ordered by count descending, then name.
- **All filament routes (including step 4's) return timestamps in the home timezone** with their UTC offset (e.g. `2026-11-22T11:53:10-06:00`), so Claude can read times aloud correctly.

## Capabilities

### New Capabilities
- `filament-search`: listing, full-text search over title, body and tag names, tag and date filters, ordering and paging, and the tag list with counts.

### Modified Capabilities
- `filament-api`: adds the requirement that returned timestamps are in the home timezone.

## Impact

- **Code:** `backend/api/filaments.py` (list route, timestamp conversion), new `backend/api/tags.py`, `backend/api/api.py` (mount `/tags`), a query module for search (`backend/filaments/queries.py`).
- **Tests:** new `backend/tests/test_api_search.py` (each filter alone and combined, ranking, paging, tag counts) and updates to `test_api_filaments.py` for local timestamps.
- **Performance:** combining tag names at query time means `q` does not use the GIN index (a scan over all live filaments). Fine at personal scale (hundreds to low thousands of rows); a stored tag-text column is the contained follow-up if it ever matters.
- **Dependencies:** none new. No migration.

## Open questions

- **Deferred decision (not decided here):** whether `list_filaments` and `search_filaments` stay separate MCP tools (step 7). Both map onto this one route either way.
