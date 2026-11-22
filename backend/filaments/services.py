"""Write logic for filaments, shared by the API (step 4) and the Phase 2 web views.

Input is already validated and normalized by the `schemas` package. Each write runs
in one transaction so a filament is never stored without the tags it was sent with.
"""

from typing import Any

from django.db import transaction

from filaments.models import Filament, Tag
from schemas import FilamentCreate


def _tags_for(names: list[str]) -> list[Tag]:
    # get_or_create retries the lookup if a parallel request created the tag first.
    return [Tag.objects.get_or_create(name=name)[0] for name in names]


@transaction.atomic
def create_filament(data: FilamentCreate, *, source: Filament.Source) -> Filament:
    filament = Filament.objects.create(title=data.title, body=data.body, source=source)
    filament.tags.set(_tags_for(data.tags))
    return filament


@transaction.atomic
def update_filament(filament: Filament, changes: dict[str, Any]) -> Filament:
    """Apply only the fields that were sent (see `FilamentUpdate.changes()`)."""
    for field in ("title", "body"):
        if field in changes:
            setattr(filament, field, changes[field])
    # Always save: a tags-only change touches only the join table, and updated_at
    # (auto_now) should still move.
    filament.save()
    if "tags" in changes:
        filament.tags.set(_tags_for(changes["tags"]))
    return filament


def soft_delete_filament(filament: Filament) -> Filament:
    filament.soft_delete()
    return filament
