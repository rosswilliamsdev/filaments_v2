"""/api/filaments: create, get, update and soft-delete single filaments.

The API's only caller is the MCP server, so every filament created here has source
`claude`. List and search (step 5) and auth (step 6) are added to this router later.
"""

import uuid

from ninja import Router, Status
from ninja.errors import HttpError

from filaments import services
from filaments.models import Filament
from schemas import ErrorDetail, FilamentCreate, FilamentOut, FilamentUpdate

router = Router(tags=["filaments"])

NOT_FOUND = "No filament with that id"


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


@router.post("", response={201: FilamentOut})
def create_filament(request, data: FilamentCreate):
    filament = services.create_filament(data, source=Filament.Source.CLAUDE)
    return Status(201, filament)


# The id is typed str, not UUID, so a malformed id reaches get_active_filament and gets
# the same JSON 404 instead of a URL-resolver 404 page or a 422 about the path.
@router.get("/{filament_id}", response={200: FilamentOut, 404: ErrorDetail})
def get_filament(request, filament_id: str):
    return get_active_filament(filament_id)


@router.patch("/{filament_id}", response={200: FilamentOut, 404: ErrorDetail})
def update_filament(request, filament_id: str, data: FilamentUpdate):
    filament = get_active_filament(filament_id)
    return services.update_filament(filament, data.changes())


@router.delete("/{filament_id}", response={200: FilamentOut, 404: ErrorDetail})
def delete_filament(request, filament_id: str):
    # Returns the filament as it was, so the MCP tool can say what it deleted.
    return services.soft_delete_filament(get_active_filament(filament_id))
