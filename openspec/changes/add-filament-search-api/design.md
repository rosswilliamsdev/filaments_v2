## Context

`Filament.search_vector` is a stored generated column (title A, body B, `english`) with a GIN index; tags are not in it because a generated column can only read its own row. `FilamentListParams`, `FilamentList` and `TagWithCount` already exist in `schemas` (step 3). The `filaments` router from step 4 has POST and per-id routes. Responses currently serialize timestamps in UTC (`…Z`).

Checked against the real Postgres:

```
to_tsvector('english', 'album-art rock-n-roll music')
  → 'album-art' 'album' 'art' 'rock-n-rol' 'rock' 'n' 'roll' 'music'
websearch_to_tsquery('english', 'album cover "hand drawn" -draft or sketch')
  → 'album' & 'cover' & 'hand' <-> 'drawn' & !'draft' | 'sketch'
websearch_to_tsquery('english', 'the')  → (empty; NOTICE, matches nothing)
```

## Goals / Non-Goals

**Goals:**
- One list route serving both "list recent" and "search" (the MCP tool split is step 7's deferred decision).
- Search that finds a note by any mix of its title, body and tag words.
- Date filters and returned timestamps that mean the user's local day and time.

**Non-Goals:**
- Excerpts/highlighting (revisit in step 7), fuzzy or typo-tolerant matching, embeddings (out of scope).
- Using the GIN index for `q` (see Risks).

## Decisions

### Where the query lives

`backend/filaments/queries.py` exposes `search_filaments(params: FilamentListParams) -> tuple[QuerySet, int]` (page queryset, total) and `tag_counts() -> QuerySet`. Routes stay thin, and Phase 2's feed view reuses the same function, mirroring `services.py` for writes.

### `q`: websearch, ANDed, against a combined vector

```
document = search_vector || setweight(to_tsvector('english', <tag names>), 'A')
WHERE document @@ websearch_to_tsquery('english', q)
ORDER BY ts_rank(document, query) DESC, created_at DESC, id DESC
```

- Tag names come from a correlated subquery: `StringAgg` of the filament's tag names, `Coalesce`d to `''` when it has none.
- The `||` concatenation reuses the stored vector: a small `Func` with `arg_joiner=" || "` and `output_field=SearchVectorField()`. **Alternative:** rebuild the whole vector at query time with `SearchVector("title", "A") + SearchVector("body", "B") + SearchVector(tags, "A")`. Rejected because it duplicates the generated column's definition, and the two could drift.
- Combining before matching (rather than `vector @@ q OR tags match q`) is what lets "music ideas" match a note tagged `music` whose body says "ideas". With AND queries, an OR of two separate matches fails when the words are split.
- `SearchQuery(q, search_type="websearch", config="english")`: never raises on user syntax; quotes, `-` and `or` work.
- Tag words weighted A: a tag is a deliberate label, as strong as a title word.

**Alternative:** a denormalized `tag_text` column feeding the generated vector (keeps the GIN index). Rejected for now: it adds a migration, a sync path in the service, an admin hook (admin tag edits bypass the service), and a change to the step 2 spec, for speed this data size doesn't need.

### Tag filter: one EXISTS per tag

For each normalized tag: `.filter(Exists(Filament.tags.through.objects.filter(filament=OuterRef("pk"), tag__name=name)))`. Joins (`filter(tags__name=…)` chained) would also work, but EXISTS keeps rows unique so `count()` is exact without `distinct()`.

### Date filter: local-midnight range

`start = make_aware(datetime.combine(date_from, time.min))`, `end = make_aware(datetime.combine(date_to + 1 day, time.min))`, both in the current (home) timezone; filter `created_at >= start` and `< end`. `make_aware` resolves DST correctly. **Not** `created_at__date`, which converts every row in SQL and hides the boundary logic.

### Ordering and paging

Always end with `-created_at, -id` so ties are deterministic. `total = qs.count()` before slicing `[offset:offset + limit]`. Responses echo the effective `limit` and `offset`.

### Route and query parameters

`@router.get("", response=FilamentList)` with `params: Query[FilamentListParams]`. Repeated `?tags=a&tags=b` fill the list field. **Risk to verify first:** that Ninja maps a repeated query key to a `list[str]` field inside a `Query[...]` model and runs the model validator (date order) with a 422. The first test checks both.

### `/api/tags`

```python
Tag.objects.annotate(count=Count("filaments", filter=Q(filaments__deleted_at__isnull=True)))
           .filter(count__gt=0).order_by("-count", "name")
```

The default manager's soft-delete filter does **not** apply to joins or annotations, so the `filter=Q(...)` is required; a test covers it. New `backend/api/tags.py` router, mounted at `/tags`. No paging.

### Timestamps in the home timezone

A helper in `api/filaments.py`, `to_out(filament) -> FilamentOut`, validates the model and replaces `created_at`/`updated_at` with `timezone.localtime(...)`. Pydantic serializes aware datetimes with their offset. All filament routes (step 4's included) return `to_out(...)`. `schemas` stays Django-free: it never sees the timezone. **Alternative:** a custom Ninja renderer converting every datetime. Rejected: broader than needed and harder to see.

## Risks / Trade-offs

- [`q` scans every live filament instead of using the GIN index] → Fine for hundreds to low thousands of rows (milliseconds). If it ever matters, move tag names into a stored column feeding the generated vector.
- [AND semantics return nothing for over-specific queries] → Claude can retry with fewer words or use `or`; step 7's tool description will say so.
- [Stop-word-only `q` silently matches nothing] → Correct by definition; returns an empty list rather than an error.
- [Ninja query-list parsing] → Verified by the first test; fallback is reading `request.GET.getlist("tags")` explicitly.
- [Large list results (full bodies)] → Revisit with excerpts in step 7 once real usage shows the size.

## Migration Plan

No database migration. Rebuild `web`. Rollback is reverting the commit.

## Open Questions

- `list_filaments` vs `search_filaments` (deferred to step 7).
