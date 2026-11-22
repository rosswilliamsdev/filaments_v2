## 1. Spike: GeneratedField search vector

- [x] 1.1 Create the `filaments` app in `backend/filaments/`, add it to `INSTALLED_APPS`, and write a minimal `Filament` with `title`, `body` and the `search_vector` `GeneratedField` (`english`, title A, body B)
- [x] 1.2 Run `makemigrations` and `migrate` against the Compose database, and inspect the column with `\d filaments_filament` to confirm a stored generated `tsvector`. If it fails, switch to a trigger-maintained `SearchVectorField`, update design.md decision 1, and continue

## 2. Models

- [x] 2.1 Add `Tag` (`name` `CharField(max_length=50, unique=True)`) with check constraints: lowercase, and no whitespace or empty names
- [x] 2.2 Complete `Filament`: UUID id, `title` (max 200), `body`, `source` choices with no default, `created_at`, `updated_at`, `deleted_at`, `tags` M2M (`related_name="filaments"`)
- [x] 2.3 Add `Filament` constraints (non-blank title and body, source in `claude`/`web`) and indexes (GIN on `search_vector`, btree on `created_at`)
- [x] 2.4 Add `ActiveFilamentManager` as the default `objects`, `all_objects` as the unfiltered manager, and a `soft_delete()` method
- [x] 2.5 Regenerate the migration as a single `0001_initial` and apply it

## 3. Admin

- [x] 3.1 Register `Tag` and `Filament`; `FilamentAdmin` lists all filaments via `all_objects`, filters on deleted/not deleted, and leaves `search_vector` out of the form

## 4. Tests (pytest-django)

- [x] 4.1 Filament fields: create with a generated UUID and timestamps; reject a 201-character title, an empty body, a whitespace-only title, and an unknown source
- [x] 4.2 Tags: reject duplicate, uppercase and whitespace-containing names; one shared tag row across two filaments; `tag.filaments` returns both
- [x] 4.3 Soft delete: `soft_delete()` sets `deleted_at`; the filament disappears from `Filament.objects` and `tag.filaments`, and stays in `Filament.all_objects`
- [x] 4.4 Search vector: a stemmed match ("running" finds "run"), title outranks body, the vector follows a queryset `update()`, and tag names are not matched
- [x] 4.5 Admin: the changelist includes a soft-deleted filament (logged-in superuser via the `admin_client` fixture)

## 5. Docs and checks

- [x] 5.1 Update `docs/backend-planning-doc.md`: remove the `search_vector` item from Deferred Decisions, note `GeneratedField` + `english` in the data model, and add "keyword search also matches tag names" under Search; mirror the data model note in `docs/PRD.md`
- [x] 5.2 Add the "keyword search also matches tag names" requirement to the step 5 entry in `roadmap.md`
- [x] 5.3 Run `uv run ruff check .`, `uv run ruff format --check .` and `uv run --env-file .env pytest`, and confirm all pass
