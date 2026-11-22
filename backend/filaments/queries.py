"""Read logic for filaments: list/search and tag counts.

Shared by the API (step 5) and the Phase 2 feed, mirroring `services.py` for writes.
"""

import datetime as dt

from django.contrib.postgres.aggregates import StringAgg
from django.contrib.postgres.search import (
    SearchQuery,
    SearchRank,
    SearchVector,
    SearchVectorField,
)
from django.db.models import (
    Count,
    Exists,
    F,
    Func,
    OuterRef,
    Q,
    QuerySet,
    Subquery,
    TextField,
    Value,
)
from django.db.models.functions import Coalesce, Concat
from django.utils import timezone

from filaments.models import Filament, Tag
from schemas import FilamentListParams

FilamentTag = Filament.tags.through

# `||` starts the right vector's positions right after the left's last word, so without a
# gap a quoted phrase could match across the body/tag join or between two tags. Stop words
# are dropped from the vector but still take up positions, so they make that gap. Eight
# covers phrases that themselves contain stop words (`"hand of the drawn"` is `<3>`).
_GAP = " " + "the " * 8


class _ConcatVectors(Func):
    """`a || b` for tsvectors, so the stored title/body vector is reused as-is."""

    arg_joiner = " || "
    template = "(%(expressions)s)"
    output_field = SearchVectorField()


def _tag_vector() -> SearchVector:
    # A generated column can only read its own row, so tag names are added at query time.
    names = (
        FilamentTag.objects.filter(filament=OuterRef("pk"))
        .values("filament")
        .annotate(names=StringAgg("tag__name", delimiter=_GAP, order_by="tag__name"))
        .values("names")
    )
    text = Concat(
        Value(_GAP),
        Coalesce(Subquery(names), Value(""), output_field=TextField()),
        output_field=TextField(),
    )
    return SearchVector(text, config="english", weight="A")


def _start_of_day(day: dt.date) -> dt.datetime:
    """Midnight at the start of `day` in the home timezone (DST-aware)."""
    return timezone.make_aware(dt.datetime.combine(day, dt.time.min))


def search_filaments(params: FilamentListParams) -> tuple[QuerySet[Filament], int]:
    """Return (the requested page, total matches). All filters combine with AND."""
    qs = Filament.objects.all()

    for name in params.tags:
        qs = qs.filter(Exists(FilamentTag.objects.filter(filament=OuterRef("pk"), tag__name=name)))

    if params.date_from:
        qs = qs.filter(created_at__gte=_start_of_day(params.date_from))
    if params.date_to and params.date_to < dt.date.max:  # the last date has no next day
        qs = qs.filter(created_at__lt=_start_of_day(params.date_to + dt.timedelta(days=1)))

    if params.q:
        query = SearchQuery(params.q, search_type="websearch", config="english")
        qs = (
            qs.annotate(document=_ConcatVectors(F("search_vector"), _tag_vector()))
            .filter(document=query)
            .annotate(rank=SearchRank(F("document"), query))
            .order_by("-rank", "-created_at", "-id")
        )
    else:
        qs = qs.order_by("-created_at", "-id")

    total = qs.count()
    page = qs.prefetch_related("tags")[params.offset : params.offset + params.limit]
    return page, total


def tag_counts() -> QuerySet:
    """Tags used by at least one live filament, most used first, as {name, count} dicts."""
    # The soft-delete default manager doesn't apply to joins, so filter deleted rows here.
    return (
        Tag.objects.annotate(count=Count("filaments", filter=Q(filaments__deleted_at__isnull=True)))
        .filter(count__gt=0)
        .order_by("-count", "name")
        .values("name", "count")
    )
