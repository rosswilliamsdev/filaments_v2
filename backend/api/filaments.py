"""/api/filaments: list/search, create, get, update and soft-delete filaments.

The API's only caller is the MCP server, so every filament created here has source
`claude`. Auth (step 6) is added to this router later.
"""

import uuid

from django.utils import timezone
from ninja import Query, Router, Status
from ninja.errors import HttpError

from filaments import queries, services
from filaments.models import Filament
from schemas import (
    ErrorDetail,
    FilamentCreate,
    FilamentList,
    FilamentListParams,
    FilamentOut,
    FilamentUpdate,
)

router = Router(tags=["filaments"])

NOT_FOUND = "No filament with that id"


def to_out(filament: Filament) -> FilamentOut:
    """Serialize a filament with timestamps in the home timezone (FILAMENTS_TIMEZONE).

    Stored values stay UTC; the offset is kept, so the instant is unchanged.
    """
    out = FilamentOut.model_validate(filament)
    return out.model_copy(
        update={
            "created_at": timezone.localtime(out.created_at),
            "updated_at": timezone.localtime(out.updated_at),
        }
    )


def get_active_filament(filament_id: str) -> Filament:
    """Look up a non-deleted filament; a missing, deleted or malformed id is a 404."""
    try:
        pk = uuid.UUID(filament_id)
    except ValueError:
        raise HttpError(404, NOT_FOUND) from None
    try:
        return Filament.objects.prefetch_related("tags").get(pk=pk)
    except Filament.DoesNotExist:
        raise HttpError(404, NOT_FOUND) from None


@router.get("", response=FilamentList)
def list_filaments(request, params: Query[FilamentListParams]):
    """List newest first, or search with `q`; tags, dates and paging filter either way."""
    page, total = queries.search_filaments(params)
    return FilamentList(
        items=[to_out(filament) for filament in page],
        total=total,
        limit=params.limit,
        offset=params.offset,
    )


@router.post("", response={201: FilamentOut})
def create_filament(request, data: FilamentCreate):
    filament = services.create_filament(data, source=Filament.Source.CLAUDE)
    return Status(201, to_out(filament))


# The id is typed str, not UUID, so a malformed id reaches get_active_filament and gets
# the same JSON 404 instead of a URL-resolver 404 page or a 422 about the path.
@router.get("/{filament_id}", response={200: FilamentOut, 404: ErrorDetail})
def get_filament(request, filament_id: str):
    return to_out(get_active_filament(filament_id))


@router.patch("/{filament_id}", response={200: FilamentOut, 404: ErrorDetail})
def update_filament(request, filament_id: str, data: FilamentUpdate):
    filament = get_active_filament(filament_id)
    return to_out(services.update_filament(filament, data.changes()))


@router.delete("/{filament_id}", response={200: FilamentOut, 404: ErrorDetail})
def delete_filament(request, filament_id: str):
    # Returns the filament as it was, so the MCP tool can say what it deleted.
    return to_out(services.soft_delete_filament(get_active_filament(filament_id)))
