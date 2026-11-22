"""Filament shapes: see the openspec shared-schemas spec."""

import datetime as dt
import uuid
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from schemas import (
    FilamentCreate,
    FilamentList,
    FilamentListParams,
    FilamentOut,
    FilamentUpdate,
)

VALID = {"title": "Album cover ideas", "body": "Matte sleeve, hand-drawn type"}


def error_for(exc: pytest.ExceptionInfo[ValidationError]) -> tuple[tuple, str]:
    """(location, message) of the single error in a ValidationError."""
    [error] = exc.value.errors()
    return error["loc"], error["msg"]


# --- Create ---------------------------------------------------------------------


def test_valid_capture_normalizes_tags():
    filament = FilamentCreate(**VALID, tags=["Music", "design"])

    assert filament.title == "Album cover ideas"
    assert filament.tags == ["music", "design"]


def test_tags_default_to_empty():
    assert FilamentCreate(**VALID).tags == []


def test_title_is_trimmed():
    assert FilamentCreate(title="  Setlist  ", body="x").title == "Setlist"


@pytest.mark.parametrize(
    ("overrides", "field"),
    [
        ({"body": " \n\t "}, "body"),
        ({"body": ""}, "body"),
        ({"title": "   "}, "title"),
        ({"title": "x" * 201}, "title"),
    ],
    ids=["whitespace-body", "empty-body", "blank-title", "title-too-long"],
)
def test_invalid_create_rejected(overrides, field):
    with pytest.raises(ValidationError) as exc:
        FilamentCreate(**{**VALID, **overrides})

    loc, _ = error_for(exc)
    assert loc == (field,)


def test_title_of_200_characters_accepted():
    assert len(FilamentCreate(**{**VALID, "title": "x" * 200}).title) == 200


def test_source_is_ignored():
    filament = FilamentCreate(**VALID, source="web")

    assert "source" not in filament.model_dump()


# --- Tag limit ------------------------------------------------------------------


def test_duplicate_tags_merged():
    assert FilamentCreate(**VALID, tags=["Music", "music ", "#music"]).tags == ["music"]


def test_nine_tags_rejected_with_speakable_message():
    with pytest.raises(ValidationError) as exc:
        FilamentCreate(**VALID, tags=[f"tag-{i}" for i in range(9)])

    assert error_for(exc) == (("tags",), "Tag limit is 8; got 9")


def test_ten_tags_that_collapse_to_eight_accepted():
    tags = [f"tag-{i}" for i in range(8)] + ["TAG-0", "#tag-1"]

    assert len(FilamentCreate(**VALID, tags=tags).tags) == 8


def test_invalid_tag_message_is_not_prefixed():
    with pytest.raises(ValidationError) as exc:
        FilamentCreate(**VALID, tags=["music", "#"])

    assert error_for(exc) == (("tags",), "Tag '#' is empty after removing punctuation")


def test_tag_limit_not_published_as_max_items():
    tags_schema = FilamentCreate.model_json_schema()["properties"]["tags"]

    assert "maxItems" not in tags_schema
    assert "Up to 8 tags" in tags_schema["description"]


# --- Update ---------------------------------------------------------------------


def test_update_reports_only_sent_fields():
    update = FilamentUpdate(title="Album cover, v2")

    assert update.changes() == {"title": "Album cover, v2"}


def test_update_with_empty_tags_clears():
    assert FilamentUpdate(tags=[]).changes() == {"tags": []}


def test_update_normalizes_and_limits_tags():
    assert FilamentUpdate(tags=["Album Art"]).changes() == {"tags": ["album-art"]}

    with pytest.raises(ValidationError):
        FilamentUpdate(tags=[f"tag-{i}" for i in range(9)])


def test_empty_update_rejected():
    with pytest.raises(ValidationError) as exc:
        FilamentUpdate()

    _, message = error_for(exc)
    assert message == "Send at least one of title, body or tags"


@pytest.mark.parametrize("field", ["title", "body", "tags"])
def test_update_rejects_null(field):
    with pytest.raises(ValidationError) as exc:
        FilamentUpdate(**{field: None})

    loc, _ = error_for(exc)
    assert loc == (field,)


def test_update_schema_does_not_offer_null():
    properties = FilamentUpdate.model_json_schema()["properties"]

    assert properties["title"]["type"] == "string"
    assert "anyOf" not in properties["title"]
    for name in ("title", "body", "tags"):
        assert "default" not in properties[name], name


# --- Output ---------------------------------------------------------------------


def make_out(**overrides) -> FilamentOut:
    now = dt.datetime(2026, 11, 22, 12, 0, tzinfo=dt.UTC)
    fields = {
        "id": uuid.uuid4(),
        **VALID,
        "tags": ["music", "design"],
        "source": "claude",
        "created_at": now,
        "updated_at": now,
        "deleted_at": None,
    }
    return FilamentOut.model_validate(SimpleNamespace(**{**fields, **overrides}))


def test_output_omits_deleted_at_and_sorts_tags():
    data = make_out().model_dump()

    assert "deleted_at" not in data
    assert data["tags"] == ["design", "music"]


class FakeManager:
    """Stands in for a Django related manager: `.all()` returns Tag-like objects."""

    def __init__(self, names):
        self._tags = [SimpleNamespace(name=n) for n in names]

    def all(self):
        return list(self._tags)


def test_output_accepts_related_manager_of_tags():
    out = make_out(tags=FakeManager(["music", "design"]))

    assert out.tags == ["design", "music"]


def test_list_shape():
    page = FilamentList(items=[make_out()], total=43, limit=20, offset=0)

    assert page.model_dump(include={"total", "limit", "offset"}) == {
        "total": 43,
        "limit": 20,
        "offset": 0,
    }


# --- List params ----------------------------------------------------------------


def test_list_params_defaults():
    params = FilamentListParams()

    assert (params.q, params.tags, params.limit, params.offset) == (None, [], 20, 0)


def test_blank_query_treated_as_absent():
    assert FilamentListParams(q="   ").q is None


def test_tag_filter_normalized_without_limit():
    assert FilamentListParams(tags=["#Music"]).tags == ["music"]
    assert len(FilamentListParams(tags=[f"t{i}" for i in range(12)]).tags) == 12


@pytest.mark.parametrize(
    ("overrides", "field"),
    [({"limit": 500}, "limit"), ({"limit": 0}, "limit"), ({"offset": -1}, "offset")],
)
def test_paging_out_of_range_rejected(overrides, field):
    with pytest.raises(ValidationError) as exc:
        FilamentListParams(**overrides)

    loc, _ = error_for(exc)
    assert loc == (field,)


def test_dates_out_of_order_rejected():
    with pytest.raises(ValidationError) as exc:
        FilamentListParams(date_from="2026-11-20", date_to="2026-11-10")

    _, message = error_for(exc)
    assert message == "Start date 2026-11-20 is after end date 2026-11-10"


def test_same_day_range_accepted():
    params = FilamentListParams(date_from="2026-11-20", date_to="2026-11-20")

    assert params.date_from == params.date_to == dt.date(2026, 11, 20)
