"""Write logic in filaments.services: see the openspec filament-api spec."""

import pytest

from filaments import services
from filaments.models import Filament, Tag
from schemas import FilamentCreate, FilamentUpdate

pytestmark = pytest.mark.django_db


def create(**overrides) -> Filament:
    fields = {"title": "Album cover ideas", "body": "Matte sleeve", "tags": ["music"]}
    return services.create_filament(
        FilamentCreate(**{**fields, **overrides}), source=Filament.Source.CLAUDE
    )


def tag_names(filament: Filament) -> list[str]:
    return sorted(filament.tags.values_list("name", flat=True))


def test_create_reuses_existing_tags_and_creates_new_ones():
    existing = Tag.objects.create(name="music")

    filament = create(tags=["Music", "Album Art"])

    assert tag_names(filament) == ["album-art", "music"]
    assert filament.tags.get(name="music") == existing
    assert Tag.objects.count() == 2
    assert filament.source == "claude"


def test_update_changes_only_sent_fields():
    filament = create()

    services.update_filament(filament, FilamentUpdate(title="Album cover, v2").changes())

    filament.refresh_from_db()
    assert (filament.title, filament.body, tag_names(filament)) == (
        "Album cover, v2",
        "Matte sleeve",
        ["music"],
    )


def test_update_replaces_and_clears_tags():
    filament = create(tags=["music", "design"])

    services.update_filament(filament, {"tags": ["art"]})
    assert tag_names(filament) == ["art"]

    services.update_filament(filament, {"tags": []})
    assert tag_names(filament) == []


def test_tags_only_update_moves_updated_at():
    filament = create()
    before = filament.updated_at

    services.update_filament(filament, {"tags": ["design"]})

    filament.refresh_from_db()
    assert filament.updated_at > before


def test_failed_tag_write_rolls_back_filament(monkeypatch):
    def boom(names):
        raise RuntimeError("tag write failed")

    monkeypatch.setattr(services, "_tags_for", boom)

    with pytest.raises(RuntimeError):
        create()

    assert Filament.all_objects.count() == 0


def test_soft_delete_returns_filament():
    filament = create()

    deleted = services.soft_delete_filament(filament)

    assert deleted.deleted_at is not None
    assert not Filament.objects.filter(pk=filament.pk).exists()
