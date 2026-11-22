"""GET /api/filaments (list/search) and GET /api/tags: see the openspec filament-search spec."""

import datetime as dt

import pytest

from filaments import services
from filaments.models import Filament
from schemas import FilamentCreate

pytestmark = pytest.mark.django_db

URL = "/api/filaments"


def make(title="Note", body="Some text", tags=(), created_at=None) -> Filament:
    filament = services.create_filament(
        FilamentCreate(title=title, body=body, tags=list(tags)), source=Filament.Source.CLAUDE
    )
    if created_at:
        Filament.objects.filter(pk=filament.pk).update(created_at=created_at)
    return filament


def titles(client, **params) -> list[str]:
    response = client.get(URL, params)
    assert response.status_code == 200, response.content
    return [item["title"] for item in response.json()["items"]]


# --- Query-parameter parsing: the riskiest assumption first ----------------------


def test_repeated_tags_param_fills_the_list(client):
    make("Both", tags=["music", "design"])
    make("Music only", tags=["music"])

    assert titles(client, tags=["music", "design"]) == ["Both"]


@pytest.mark.parametrize(
    ("params", "field"),
    [({"limit": 500}, "limit"), ({"date_from": "2026-11-20", "date_to": "2026-11-10"}, "date_to")],
    ids=["limit", "date-order"],
)
def test_invalid_params_are_422_on_the_field(client, params, field):
    response = client.get(URL, params)

    assert response.status_code == 422
    [error] = response.json()["detail"]
    assert error["loc"][-1] == field
    if field == "date_to":
        assert error["msg"] == "Start date 2026-11-20 is after end date 2026-11-10"


# --- Listing --------------------------------------------------------------------


def test_default_listing_is_newest_twenty_with_total(client):
    base = dt.datetime(2026, 11, 1, tzinfo=dt.UTC)
    for i in range(25):
        make(f"Note {i:02d}", created_at=base + dt.timedelta(hours=i))

    data = client.get(URL).json()

    assert (data["total"], data["limit"], data["offset"]) == (25, 20, 0)
    assert [item["title"] for item in data["items"]] == [f"Note {i:02d}" for i in range(24, 4, -1)]


def test_paging_never_repeats_or_skips_with_identical_timestamps(client):
    same_moment = dt.datetime(2026, 11, 1, tzinfo=dt.UTC)
    for i in range(25):
        make(f"Note {i:02d}", created_at=same_moment)

    first = titles(client)
    second = titles(client, offset=20)

    assert len(first) == 20 and len(second) == 5
    assert set(first).isdisjoint(second)
    assert len(set(first) | set(second)) == 25


def test_soft_deleted_filaments_are_excluded(client):
    make("Kept")
    make("Gone").soft_delete()

    data = client.get(URL).json()

    assert [item["title"] for item in data["items"]] == ["Kept"]
    assert data["total"] == 1
    assert titles(client, q="gone") == []


# --- Keyword search -------------------------------------------------------------


def test_search_stems_words(client):
    make("Morning", "I went for a run by the river")

    assert titles(client, q="running") == ["Morning"]


def test_search_matches_tag_name_only(client):
    make("Album cover ideas", "Matte sleeve", tags=["music"])

    assert titles(client, q="music") == ["Album cover ideas"]


def test_search_words_split_across_tag_and_body(client):
    make("Sketchbook", "Some ideas for later", tags=["music"])
    make("Other", "Some ideas for later")

    assert titles(client, q="music ideas") == ["Sketchbook"]


def test_hyphenated_tag_matches_separate_words(client):
    make("Cover", "Matte sleeve", tags=["album-art"])

    assert titles(client, q="album art") == ["Cover"]


def test_all_words_required(client):
    make("Harmony only", "A note about harmony")
    make("Both", "Harmony in the bridge")

    assert titles(client, q="harmony bridge") == ["Both"]


def test_title_outranks_body(client):
    make("Harmony notes", "Ideas for the bridge")
    make("Bridge ideas", "Try a vocal harmony here")

    assert titles(client, q="harmony") == ["Harmony notes", "Bridge ideas"]


def test_phrase_and_exclusion(client):
    make("Sleeve", "A hand drawn sleeve")
    make("Draft", "A hand drawn draft")
    make("Reversed", "Drawn by hand")

    assert titles(client, q='"hand drawn" -draft') == ["Sleeve"]


def test_phrase_does_not_match_across_tags_or_the_body_tag_join(client):
    make("Body then tag", "Notes on the cover, hand", tags=["drawn"])
    make("Two tags", "Unrelated", tags=["hand", "drawn"])
    make("Real phrase", "A hand drawn sleeve")
    make("Hyphenated tag", "Unrelated", tags=["hand-drawn"])

    assert sorted(titles(client, q='"hand drawn"')) == ["Hyphenated tag", "Real phrase"]


def test_only_stop_words_returns_empty(client):
    make("The note", "The the the")

    data = client.get(URL, {"q": "the"}).json()

    assert (data["items"], data["total"]) == ([], 0)


# --- Tag and date filters -------------------------------------------------------


def test_tag_filter_is_normalized_and_unknown_tag_is_empty(client):
    make("Song", tags=["music"])

    assert titles(client, tags="#Music") == ["Song"]
    assert titles(client, tags="nothing-here") == []


def test_date_filter_uses_home_timezone(client, settings):
    settings.TIME_ZONE = "America/Chicago"
    # 23:30 on Nov 24 in Chicago is 05:30 UTC on Nov 25.
    make("Late idea", created_at=dt.datetime(2026, 11, 25, 5, 30, tzinfo=dt.UTC))

    assert titles(client, date_from="2026-11-24", date_to="2026-11-24") == ["Late idea"]
    assert titles(client, date_from="2026-11-25", date_to="2026-11-25") == []
    assert titles(client, date_to="2026-11-24") == ["Late idea"]
    assert titles(client, date_to="9999-12-31") == ["Late idea"]  # no overflow at date.max


def test_all_filters_combine(client, settings):
    settings.TIME_ZONE = "America/Chicago"
    inside = dt.datetime(2026, 11, 10, 18, tzinfo=dt.UTC)
    outside = dt.datetime(2026, 11, 20, 18, tzinfo=dt.UTC)
    make("Match", "New cover art", tags=["music"], created_at=inside)
    make("Wrong tag", "New cover art", tags=["design"], created_at=inside)
    make("Wrong date", "New cover art", tags=["music"], created_at=outside)
    make("Wrong words", "Setlist", tags=["music"], created_at=inside)

    data = client.get(
        URL, {"q": "cover", "tags": "music", "date_from": "2026-11-09", "date_to": "2026-11-11"}
    ).json()

    assert [item["title"] for item in data["items"]] == ["Match"]
    assert data["total"] == 1


# --- /api/tags ------------------------------------------------------------------


def test_tag_counts_exclude_soft_deleted_and_hide_unused(client):
    make("One", tags=["music"])
    make("Two", tags=["music"])
    make("Three", tags=["music", "lonely"]).soft_delete()
    replaced = make("Four", tags=["old-tag"])
    services.update_filament(replaced, {"tags": []})

    assert client.get("/api/tags").json() == [{"name": "music", "count": 2}]


def test_tags_ordered_by_count_then_name(client):
    for _ in range(5):
        make(tags=["music"])
    for _ in range(2):
        make(tags=["design", "art"])

    names = [tag["name"] for tag in client.get("/api/tags").json()]

    assert names == ["music", "art", "design"]
