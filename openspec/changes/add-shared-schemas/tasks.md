## 1. Tag normalization

- [x] 1.1 Create `schemas/src/schemas/tags.py` with `MAX_TAGS`, `MAX_TAG_LENGTH`, `normalize_tag()` (trim, lowercase, strip accents, `[\W_]+` → `-`, trim `-`, reject empty / over 50 with speakable `ValueError` messages) and `normalize_tags()` (normalize + dedupe keeping order)
- [x] 1.2 Add `TagWithCount` (`name`, `count`) to `tags.py`
- [x] 1.3 Add `schemas/tests/test_tags.py`: spaces, `#`, apostrophes, `_`, accents, non-Latin, empty-after-normalization, 50 vs 51 characters, dedupe order

## 2. Filament shapes

- [x] 2.1 Create `schemas/src/schemas/filaments.py` with a reusable tag-list type (`AfterValidator` running `normalize_tags` then the 8-tag check, "Tag limit is 8; got N"; limit stated in the field description, no `maxItems`)
- [x] 2.2 Add `FilamentCreate` (stripped 1–200 title, non-blank body, tags default `[]`; no `source`)
- [x] 2.3 Add `FilamentUpdate` (all optional, explicit `null` rejected for title/body/tags) with a `changes()` helper built on `model_fields_set`
- [x] 2.4 Add `FilamentOut` (no `deleted_at`, `tags: list[str]`, `from_attributes=True`) and `FilamentList` (`items`, `total`, `limit`, `offset`)
- [x] 2.5 Add `FilamentListParams` (`q` blank → `None`, normalized tag filter with no count limit, inclusive dates with `date_from <= date_to`, `limit` 1–100 default 20, `offset` ≥ 0 default 0)
- [x] 2.6 Re-export all public names from `schemas/__init__.py`
- [x] 2.7 Add `schemas/tests/test_filaments.py` covering every scenario in `specs/shared-schemas/spec.md` (create, update incl. `model_fields_set`, output, list params, 8 vs 9 tags, 10 that collapse to 8, `source` ignored)
- [x] 2.8 Add `schemas/tests/test_no_django.py`: subprocess import of `schemas` leaves no `django` modules loaded; check the JSON schema of the tag field has no `maxItems`

## 3. Home timezone

- [x] 3.1 In `backend/config/settings.py`, read `FILAMENTS_TIMEZONE` (default `UTC`), validate with `zoneinfo.ZoneInfo` (raise `ImproperlyConfigured` naming the setting), assign to `TIME_ZONE`; keep `USE_TZ = True`
- [x] 3.2 Add `FILAMENTS_TIMEZONE=America/Chicago` to `.env.example` (with a comment) and the local `.env`; make sure `compose.yaml`'s `web` service receives it
- [x] 3.3 Add `backend/tests/test_timezone.py`: a filament created at 05:30 UTC on 2026-11-25 has local date 2026-11-24 under `America/Chicago`; an unknown zone raises `ImproperlyConfigured`

## 4. Wiring and docs

- [x] 4.1 Add `schemas/tests` to pytest `testpaths` in the root `pyproject.toml`
- [x] 4.2 Update the tag rule in `CLAUDE.md`, `docs/backend-planning-doc.md`, `docs/PRD.md` and `roadmap.md` to the full normalization rule; add `FILAMENTS_TIMEZONE` to the CLAUDE.md Commands section and update the Tag model docstring
- [x] 4.3 Run `uv run --env-file .env pytest` (all pass) and `uv run ruff check . && uv run ruff format .`
