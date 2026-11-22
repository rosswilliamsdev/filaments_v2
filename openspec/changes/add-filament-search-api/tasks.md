## 1. Timestamps in the home timezone

- [ ] 1.1 Add `to_out(filament)` in `backend/api/filaments.py` converting `created_at`/`updated_at` with `timezone.localtime`; use it in every step 4 route
- [ ] 1.2 Test in `backend/tests/test_api_filaments.py`: under `America/Chicago`, a filament at 17:53:10 UTC returns `…T11:53:10…-06:00`, and the instant equals the stored UTC value

## 2. Search query module

- [ ] 2.1 Create `backend/filaments/queries.py` with `search_filaments(params) -> (page, total)`: combined `search_vector || setweight(tag vector, 'A')`, websearch `SearchQuery`, rank ordering, `-created_at, -id` tiebreak, one `Exists` per tag, local-midnight date range
- [ ] 2.2 Add `tag_counts()`: count non-deleted filaments per tag, hide zero, order by count desc then name

## 3. Routes

- [ ] 3.1 Add `GET /api/filaments` (`Query[FilamentListParams]` → `FilamentList`) to the filaments router
- [ ] 3.2 Create `backend/api/tags.py` with `GET /api/tags` → `list[TagWithCount]`; mount at `/tags` in `backend/api/api.py`

## 4. Tests

- [ ] 4.1 In new `backend/tests/test_api_search.py`, first verify Ninja parses repeated `?tags=` into the list and returns 422 for out-of-order dates and `limit=500`
- [ ] 4.2 Listing: default page of 20 newest with `total`, second page with no repeats (including identical `created_at`), soft-deleted excluded
- [ ] 4.3 Keyword search: stemming, tag-only match, words split across tag and body, hyphenated tag vs "album art", AND semantics, title outranks body, phrase + exclusion, stop-words-only returns empty
- [ ] 4.4 Tag filter (all must match, normalized, unknown tag empty), date filter (late-evening Chicago note on its local day, not the next), and all filters combined with exact `total`
- [ ] 4.5 `/api/tags`: counts exclude soft-deleted filaments, zero-count tags hidden, ordering by count then name

## 5. Docs and checks

- [ ] 5.1 Update `docs/backend-planning-doc.md` Search section (websearch syntax, tags combined at query time, local timestamps) and CLAUDE.md layout (`filaments/queries.py`)
- [ ] 5.2 Run `uv run --env-file .env pytest` and `uv run ruff check . && uv run ruff format .`; smoke-test list, search and tags with curl against `docker compose up -d --build`
