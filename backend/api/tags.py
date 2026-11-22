"""/api/tags: tags in use, with how many live filaments carry each."""

from ninja import Router

from filaments import queries
from schemas import TagWithCount

router = Router(tags=["tags"])


@router.get("", response=list[TagWithCount])
def list_tags(request):
    return list(queries.tag_counts())
