## Context

Step 1 left a Django 5.2 project (`backend/config`, `backend/api`) on Postgres 17 with `django.contrib.postgres` installed and no models. `docs/backend-planning-doc.md` defines the entities, soft delete and search weighting, and defers one decision to this step: how `search_vector` stays current. Exploration on 2026-11-21 settled three more points: body is required, search uses the `english` config, and keyword search will also match tag names (implemented in step 5, not in the vector).

```
┌──────────────────────────────┐        ┌─────────────────────┐
│ filaments_filament           │        │ filaments_tag       │
│  id            uuid  PK      │  M2M   │  id    bigint PK    │
│  title         varchar(200)  │◀──────▶│  name  varchar(50)  │
│  body          text          │        │        UNIQUE       │
│  source        varchar(10)   │        └─────────────────────┘
│  search_vector tsvector GEN  │  ← GIN index
│  created_at    timestamptz   │  ← btree index
│  updated_at    timestamptz   │
│  deleted_at    timestamptz ? │
└──────────────────────────────┘
```

## Goals / Non-Goals

**Goals:**
- `Filament` and `Tag` tables with the fields in `docs/backend-planning-doc.md`.
- A `search_vector` that can't go stale, however a row is written.
- Database constraints that reject empty titles and bodies, unknown sources, and malformed tag names, even if a caller bypasses the schemas.
- Soft-deleted filaments are hidden by default everywhere, including through `tag.filaments`.

**Non-Goals:**
- Tag normalization and the 8-tag limit. Those are validators in the `schemas` package (step 3). The database can't cheaply count M2M rows per filament.
- Any API route, schema or business-logic module (steps 3–4).
- Matching tag names in keyword search (step 5).
- The 30-day purge command (step 10). This change only provides the `all_objects` manager it needs.

## Decisions

### 1. `search_vector` is a `GeneratedField`

```python
search_vector = GeneratedField(
    expression=SearchVector("title", weight="A", config="english")
    + SearchVector("body", weight="B", config="english"),
    output_field=SearchVectorField(),
    db_persist=True,
)
```

Postgres computes the column on every insert and update, so it stays correct after `save()`, `queryset.update()`, bulk operations or raw SQL.

**Alternatives:**
- *Update in `save()` or a signal:* `queryset.update()` and bulk writes skip it, and the vector goes stale silently.
- *Postgres trigger:* just as robust, but raw SQL in a migration that Django doesn't know about. **This is the fallback** if the spike below fails.

**Spike first (task 1.1):** Postgres only allows *immutable* expressions in generated columns. `to_tsvector('english'::regconfig, …)` with a literal config is immutable, but Django has had bugs compiling `SearchVector` (its config parameter, `COALESCE` wrapping) into generated-column DDL. The first task writes the field, runs `makemigrations` and `migrate`, and inspects the column with `\d filaments_filament`. If it fails, switch to the trigger and update this section before continuing.

**Consequence:** tags can't be in the vector, because a generated column reads only its own row. This matches the agreed approach: step 5 matches `q` against the vector **or** tag names.

**Caveat:** Django doesn't reload a generated column after `save()` on every backend. Code (and tests) that need the new value must call `refresh_from_db()`. In practice nothing reads `search_vector` back; it's only used in `WHERE` and `ORDER BY`.

### 2. Text-search config `english`, fixed in the column

The generated column uses `english`, so every query in step 5 must use `SearchQuery(..., config="english")`. A mismatched config doesn't fail, it just misses matches. Changing the config later means a migration that rebuilds the column, which is cheap at this scale.

### 3. Field rules and constraints

| Field | Django | Database constraint |
|---|---|---|
| `id` | `UUIDField(primary_key, default=uuid4, editable=False)` | — |
| `title` | `CharField(max_length=200)` | `CHECK (title ~ '\S')`: at least one non-space character |
| `body` | `TextField()` | `CHECK (body ~ '\S')`: body is required (agreed) |
| `source` | `CharField(max_length=10, choices=Source)` with **no default** | `CHECK (source IN ('claude','web'))` |
| `created_at` | `auto_now_add` | indexed (newest-first ordering and date filters) |
| `updated_at` | `auto_now` | — |
| `deleted_at` | `null=True, blank=True` | — |
| `tags` | `ManyToManyField(Tag, related_name="filaments", blank=True)` | — |
| `Tag.name` | `CharField(max_length=50, unique=True)` | `CHECK (name = lower(name))`, `CHECK (name ~ '^\S+$')` |

No default for `source`: every write path must say where the note came from.

The tag constraints are a **backstop**, not the normalization rules. Step 3 normalizes (trim, lowercase, spaces to hyphens) before anything reaches the database. The database just refuses anything that slipped through unnormalized.

**`uuid4`, not `uuid7`:** Python 3.13 and Postgres 17 have no built-in `uuid7`, and ordering uses `created_at`, not the id.

### 4. Two managers: `objects` hides deleted rows, `all_objects` doesn't

```python
class ActiveFilamentManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(deleted_at__isnull=True)


class Filament(models.Model):
    objects = ActiveFilamentManager()  # declared first → default manager
    all_objects = models.Manager()
```

- Because `objects` is the default manager, related access such as `tag.filaments.all()` also hides deleted filaments, so step 5's tag counts are correct without extra filtering. A test locks this in.
- Django's *base* manager (used when following a foreign key) stays unfiltered, which is the Django default. That's correct: a relation to a deleted row shouldn't silently become `None`.
- `soft_delete()` sets `deleted_at = now()` and saves only that field. Restoring a deleted filament isn't in scope.

**Alternative:** a `deleted` boolean plus a timestamp. That's redundant, because `deleted_at IS NOT NULL` already says it.

### 5. Admin shows everything

`FilamentAdmin.get_queryset` uses `all_objects`, with a list filter on whether `deleted_at` is set. Otherwise soft-deleted filaments would be invisible everywhere until the purge. `search_vector` isn't editable, so it's left out of the form.

### 6. Where it lives

A new app at `backend/filaments/` (`models.py`, `admin.py`, `migrations/`), added to `INSTALLED_APPS`. The app holds models only. Where business logic goes is an open question for step 4.

## Risks / Trade-offs

- **`GeneratedField` + `SearchVector` DDL fails or isn't immutable** → spike in task 1.1. Fall back to a trigger-maintained `SearchVectorField`, and record the switch here.
- **`english` stemming over-matches** (e.g. "organ" and "organization" can stem alike) → accepted for spoken search. The config can be changed later with a column rebuild.
- **`updated_at` (`auto_now`) doesn't change when only tags change** → step 4 must save the filament whenever its tags change. Noted for that proposal.
- **The default manager hides rows from code that expects them** (e.g. a future restore feature) → use `all_objects` explicitly. The name makes the intent visible.

## Migration Plan

The first app migration (`filaments/0001_initial`) runs automatically on `docker compose up` (the `web` command runs `migrate`). There's no existing data. Rollback: `migrate filaments zero`.

## Open Questions

- Where business logic lives (service module vs. routes). Decide in step 4.
- After archive, update `docs/backend-planning-doc.md` → Deferred Decisions (remove the `search_vector` item) and note `english` in the data model section.
