## Why

Every later step stores or reads filaments: the shared schemas (step 3), the API (steps 4–5), the MCP tools (step 7) and the nightly purge (step 10). This change adds the `Filament` and `Tag` tables they all build on, and settles the deferred decision on how `search_vector` stays current. Roadmap step 2, **Phase 1 (voice capture, MVP)**.

## What Changes

- Add a `filaments` Django app with two models:
  - `Filament`: UUID id, `title`, `body` (Markdown), `source` (`claude` | `web`), `search_vector`, `created_at`, `updated_at`, `deleted_at`, and a many-to-many to `Tag`.
  - `Tag`: unique lowercase `name`.
- `search_vector` is a Postgres generated column: title weighted A, body weighted B, using the `english` text-search config, with a GIN index. **Settles the deferred decision** (`GeneratedField` vs. update on save) in favour of `GeneratedField`, subject to a spike in the first task.
- Database-level rules: `title` and `body` must be non-empty, `title` has a maximum length, and tag names must be non-empty, lowercase and free of whitespace.
- A default manager that hides soft-deleted filaments, plus an unfiltered `all_objects` manager for the purge and the admin.
- Register both models in the Django admin, so deleted filaments are still visible there.
- Model tests for the constraints, the soft-delete managers and the search vector.

## Capabilities

### New Capabilities
- `filament-storage`: how filaments and tags are stored, which values the database accepts, how soft-deleted filaments are hidden, and how the full-text search vector is kept current.

### Modified Capabilities
_None._ `api-health` is unchanged.

## Impact

- **New code:** `backend/filaments/` (models, managers, admin, migrations) and `backend/tests/test_models.py`. `config/settings.py` adds the app to `INSTALLED_APPS`.
- **Dependencies:** none new. `django.contrib.postgres` is already installed.
- **Schemas package:** untouched. Request and response shapes arrive in step 3.

### Decisions made for this change (agreed in exploration, 2026-11-21)
- **Body is required.** A filament always has a non-empty body. Title-only notes aren't allowed.
- **Text-search config is `english`** (stemming and stop words), so spoken search terms match other forms of the same word.
- **Keyword search will also match tag names.** This is a **requirement for step 5** (`GET /api/filaments?q=`), recorded here so it isn't lost. It is why tags are *not* part of `search_vector`: a generated column can only read its own row, so step 5 will match `q` against both the vector and tag names.

### Conflicts with planning docs
- None. `docs/backend-planning-doc.md` lists `GeneratedField` vs. update on save as deferred to this step. Once this change is archived, that entry and the PRD data model note should say `GeneratedField`, `english`.

### Open questions (not decided here)
- **Where business logic lives** (a service module shared by Ninja routes and Phase 2 views vs. logic in the routes). It first matters in step 4. Flagged so step 4's proposal decides it.
- **Tag name format beyond the basics** (punctuation, underscores, accents, maximum length rules in the schema). That belongs to step 3's normalization rules. The database only guarantees non-empty, lowercase and no whitespace.
