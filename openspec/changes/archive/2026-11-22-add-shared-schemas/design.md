## Context

`schemas` exists as a uv workspace member (`filaments-schemas`, import name `schemas`) holding only `ErrorDetail` and `HealthStatus`. The database (step 2) already rejects uppercase tags, tags with whitespace, empty tags, tags over 50 characters, and blank titles or bodies, but those are backstops that produce 500-style integrity errors. This change puts the friendly, retryable validation in front of them.

```
 Claude (MCP) ─┐                                     ┌─ normalize, dedupe, limit ─┐
               ├──▶ schemas (Pydantic, no Django) ───┤                            ├──▶ API ──▶ DB constraints
 web UI (P2) ──┘                                     └─ speakable error text ─────┘           (backstop)
```

Because the MCP server (step 7) imports the same models, Claude's input is validated before any HTTP call.

## Goals / Non-Goals

**Goals:**
- One definition of every filament/tag request and response shape.
- Tag normalization that is predictable, testable without a database, and reusable outside Pydantic.
- Error messages that make sense read aloud.
- A home timezone so "last Tuesday" means the user's Tuesday.

**Non-Goals:**
- The routes that use these shapes (steps 4–5) and applying the timezone to filters (step 5).
- Deciding whether `list_filaments` and `search_filaments` merge (deferred to step 7).
- Deciding where write logic lives (step 4).

## Decisions

### Module layout

| Module | Contents |
|---|---|
| `schemas/tags.py` | `MAX_TAGS = 8`, `MAX_TAG_LENGTH = 50`, `normalize_tag(str) -> str`, `normalize_tags(list[str]) -> list[str]` (normalize + dedupe, no count check), `TagWithCount` |
| `schemas/filaments.py` | `FilamentCreate`, `FilamentUpdate`, `FilamentOut`, `FilamentListParams`, `FilamentList` |
| `schemas/common.py` | unchanged (`ErrorDetail`, `HealthStatus`) |
| `schemas/__init__.py` | re-exports all public names |

Plain functions in `tags.py` let Phase 2 Django views or a management command normalize tags without building a model.

### Normalization pipeline

`strip()` → `lower()` → `unicodedata.normalize("NFKD")` and drop combining marks → `re.sub(r"[\W_]+", "-")` → `strip("-")`. Then reject if empty, reject if over 50.

- **`[\W_]+`, not `[^\w]+`:** `\w` includes `_`, so `album_art` would survive. Both forms are Unicode-aware, so Cyrillic or CJK letters are kept.
- **Lowercase before stripping accents** so `É` and `é` take the same path. `lower()` is used rather than `casefold()` to keep the rule simple to explain; `ß` stays `ß`.
- **Known gap:** NFKD can't split letters like `ø`, `ł` or `ß`, so they stay as they are. Acceptable for personal notes, and the DB still accepts them (lowercase, no whitespace).
- **Alternative considered:** only spaces to hyphens (the original doc wording). Rejected because `#music` vs `music` and `album_art` vs `album-art` would quietly become separate tags, and Claude often adds `#`.

### Limit after dedupe, enforced in a validator

The tag field is `list[str]` with an `AfterValidator` that runs `normalize_tags`, then checks `len > MAX_TAGS`. **Not** `Field(max_length=8)`: Pydantic checks field constraints before validators (so it would count duplicates), and it would publish `maxItems: 8` in the JSON schema Claude sees. The field's `description` says "Up to 8 tags; normalized to lowercase-hyphenated" so Claude still knows the rule.

Messages are written for speech: "Tag limit is 8; got 10", "Tag '#' is empty after removing punctuation", "Tag 'x…' is longer than 50 characters". Pydantic places them in the 422 body under the field's location, and step 7 passes them through.

### Title and body

- `title`: stripped, then 1–200 characters (`StringConstraints(strip_whitespace=True, min_length=1, max_length=200)`).
- `body`: stored as sent (Markdown whitespace can matter), but must contain a non-whitespace character. No length cap; dictated notes are short and Postgres `text` is unbounded.

### PATCH semantics via `model_fields_set`

`FilamentUpdate` fields default to `None`, and validators reject an explicit `None` for `title`/`body`. Step 4 reads `model_fields_set` (exposed as a small `changes()` helper returning a dict of sent fields) to tell "omitted" from "sent". No sentinel types, which keeps the JSON schema simple for FastMCP.

`tags: null` is treated like `null` title: rejected. Clearing uses `[]`.

### Unknown fields are ignored

Pydantic's default `extra="ignore"` is kept, so a stray `source` is dropped. **Alternative:** `extra="forbid"`, which would catch typos like `tag` instead of `tags`. Rejected for now because FastMCP builds tool arguments from the schema, so Claude can't send undeclared fields through the MCP path anyway; the API is localhost-only.

### Output shapes

`FilamentOut.tags` is `list[str]` sorted by name, so results read the same way every time. `FilamentOut` has `from_attributes=True`; turning the M2M manager into names happens in the API layer (step 4) since `schemas` can't touch Django objects beyond attribute reads. `FilamentList` uses `total` so Claude can say "showing 10 of 43".

### List parameters

`FilamentListParams` is a flat model: `q: str | None` (blank → `None`), `tags: list[str]` (normalized, deduped, no count limit; an empty-after-normalization tag is rejected), `date_from`/`date_to: date | None` (inclusive), `limit: int = Field(20, ge=1, le=100)`, `offset: int = Field(0, ge=0)`, and a model validator rejecting `date_from > date_to`. Ninja can take it as `Query[FilamentListParams]`; FastMCP can expose the same fields as tool arguments.

### Home timezone

`settings.py` reads `FILAMENTS_TIMEZONE` (default `UTC`), validates it with `zoneinfo.ZoneInfo` (raising `ImproperlyConfigured` on failure) and assigns it to `TIME_ZONE`. `USE_TZ = True` stays, so Postgres stores UTC and `timezone.localdate()` / `localtime()` use the home zone. `schemas` only declares `date` types; conversion to datetime ranges is step 5.

**Alternative considered:** accept ISO datetimes with offsets and let Claude compute ranges. Rejected: it depends on Claude knowing the user's zone and doing date arithmetic correctly.

**Default `UTC` vs. required:** a default keeps tests and fresh checkouts working; `.env.example` sets `America/Chicago` so a real install picks it up.

### Tests

`schemas/tests/` runs without a database and is added to `testpaths`. The no-Django test runs `python -c "import schemas, schemas.tags, schemas.filaments; import sys; assert not any(m == 'django' or m.startswith('django.') for m in sys.modules)"` in a subprocess, because pytest-django has already imported Django in the test process.

## Risks / Trade-offs

- [Normalization merges tags the user meant to keep apart, e.g. `c++` → `c`] → Rare for personal notes; the rule is documented and tested, and the user can rename tags in the admin.
- [Docs say "spaces to hyphens"; code does more] → This change updates CLAUDE.md, the backend planning doc, the PRD and the roadmap in the same commit.
- [Existing tags created before this rule] → None yet (no real data), so no data migration.
- [Wrong home timezone after travel] → Dates are interpreted in the configured zone; changing `FILAMENTS_TIMEZONE` is a restart. Stored timestamps are UTC, so nothing is lost.
- [Pydantic error text wording changes between versions] → Only our own messages are asserted in tests; Pydantic's built-in ones (e.g. `limit` range) are checked by field location, not text.

## Migration Plan

No database migration. Deploy is: add `FILAMENTS_TIMEZONE` to `.env`, rebuild `web`. Rollback is reverting the commit.

## Open Questions

- `list_filaments` vs. `search_filaments` (deferred to step 7); the params schema serves either.
- Where write logic lives and how `source` is set for web writes (step 4).
