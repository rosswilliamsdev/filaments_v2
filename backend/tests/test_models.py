"""Filament and Tag storage rules: see the openspec filament-storage spec."""

import uuid

import pytest
from django.contrib.postgres.search import SearchQuery, SearchRank
from django.db import DataError, IntegrityError, transaction
from django.db.models import F

from filaments.models import Filament, Tag

pytestmark = pytest.mark.django_db


def make_filament(**overrides) -> Filament:
    fields = {
        "title": "Album cover ideas",
        "body": "Matte sleeve, hand-drawn type",
        "source": "claude",
    }
    fields.update(overrides)
    return Filament.objects.create(**fields)


def search(term: str):
    return Filament.objects.filter(search_vector=SearchQuery(term, config="english"))


# --- 4.1 Filament fields --------------------------------------------------------


def test_create_sets_uuid_and_timestamps():
    filament = make_filament()

    assert isinstance(filament.id, uuid.UUID)
    assert filament.created_at is not None
    assert filament.updated_at is not None
    assert filament.deleted_at is None


@pytest.mark.parametrize(
    ("overrides", "error"),
    [
        ({"title": "x" * 201}, DataError),
        ({"body": ""}, IntegrityError),
        ({"body": " \n\t "}, IntegrityError),
        ({"title": "   "}, IntegrityError),
        ({"source": "email"}, IntegrityError),
    ],
    ids=["title-too-long", "empty-body", "whitespace-body", "whitespace-title", "unknown-source"],
)
def test_invalid_filament_rejected(overrides, error):
    with pytest.raises(error), transaction.atomic():
        make_filament(**overrides)


# --- 4.2 Tags -------------------------------------------------------------------


@pytest.mark.parametrize(
    ("name", "error"),
    [
        ("Music", IntegrityError),
        ("album art", IntegrityError),
        ("", IntegrityError),
        ("x" * 51, DataError),
    ],
    ids=["uppercase", "whitespace", "empty", "too-long"],
)
def test_invalid_tag_rejected(name, error):
    with pytest.raises(error), transaction.atomic():
        Tag.objects.create(name=name)


def test_duplicate_tag_rejected():
    Tag.objects.create(name="music")

    with pytest.raises(IntegrityError), transaction.atomic():
        Tag.objects.create(name="music")


def test_tag_shared_by_filaments():
    music = Tag.objects.create(name="music")
    first = make_filament(title="Album cover ideas")
    second = make_filament(title="Setlist for Friday")
    first.tags.add(music)
    second.tags.add(music)

    assert Tag.objects.filter(name="music").count() == 1
    assert set(music.filaments.all()) == {first, second}


# --- 4.3 Soft delete ------------------------------------------------------------


def test_soft_delete_hides_filament_by_default():
    music = Tag.objects.create(name="music")
    kept = make_filament(title="Kept")
    deleted = make_filament(title="Deleted")
    kept.tags.add(music)
    deleted.tags.add(music)

    deleted.soft_delete()

    deleted.refresh_from_db(from_queryset=Filament.all_objects.all())
    assert deleted.deleted_at is not None
    assert list(Filament.objects.all()) == [kept]
    assert list(music.filaments.all()) == [kept]
    assert set(Filament.all_objects.all()) == {kept, deleted}


# --- 4.4 Search vector ----------------------------------------------------------


def test_search_stems_english_words():
    filament = make_filament(title="Morning", body="I went for a run by the river")

    assert list(search("running")) == [filament]


def test_title_outranks_body():
    in_title = make_filament(title="Harmony notes", body="Ideas for the bridge")
    in_body = make_filament(title="Bridge ideas", body="Try a vocal harmony here")
    query = SearchQuery("harmony", config="english")

    ranked = (
        Filament.objects.filter(search_vector=query)
        .annotate(rank=SearchRank(F("search_vector"), query))
        .order_by("-rank")
    )

    assert list(ranked) == [in_title, in_body]


def test_vector_follows_queryset_update():
    filament = make_filament(title="Garden", body="Plant tomatoes in spring")

    Filament.objects.filter(pk=filament.pk).update(body="Prune the roses in autumn")

    assert list(search("roses")) == [filament]
    assert list(search("tomatoes")) == []


def test_tag_names_not_in_vector():
    filament = make_filament(title="Album cover ideas", body="Matte sleeve, hand-drawn type")
    filament.tags.add(Tag.objects.create(name="music"))

    assert list(search("music")) == []


# --- 4.5 Admin ------------------------------------------------------------------


def test_admin_lists_soft_deleted_filaments(admin_client):
    make_filament(title="Still here")
    gone = make_filament(title="Deleted note")
    gone.soft_delete()

    response = admin_client.get("/admin/filaments/filament/")
    deleted_only = admin_client.get("/admin/filaments/filament/?deleted=yes")

    assert response.status_code == 200
    assert "Still here" in response.text
    assert "Deleted note" in response.text
    assert "Deleted note" in deleted_only.text
    assert "Still here" not in deleted_only.text
