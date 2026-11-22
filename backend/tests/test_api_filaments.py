"""/api/filaments create/get/update/delete: see the openspec filament-api spec."""

import datetime as dt
import json
import logging

import pytest

from filaments import services
from filaments.models import Filament, Tag

pytestmark = pytest.mark.django_db

URL = "/api/filaments"
NOT_FOUND = {"detail": "No filament with that id"}
CAPTURE = {
    "title": "Album cover ideas",
    "body": "Matte sleeve, hand-drawn type",
    "tags": ["Music", "design"],
}


def send(client, method: str, url: str, payload) -> object:
    if method == "get":  # the test client treats GET data as query parameters
        return client.get(url)
    return getattr(client, method)(url, json.dumps(payload), content_type="application/json")


@pytest.fixture
def filament(client) -> dict:
    response = send(client, "post", URL, CAPTURE)
    assert response.status_code == 201
    return response.json()


def errors(response) -> list[tuple[str, str]]:
    """(last location segment, message) for each validation error."""
    return [(e["loc"][-1], e["msg"]) for e in response.json()["detail"]]


# --- Update: the riskiest assumption first ---------------------------------------


def test_patch_title_only_keeps_body_and_tags(client, filament):
    # FilamentUpdate.changes() relies on model_fields_set surviving Ninja's body parsing.
    response = send(client, "patch", f"{URL}/{filament['id']}", {"title": "Album cover, v2"})

    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Album cover, v2"
    assert data["body"] == CAPTURE["body"]
    assert data["tags"] == ["design", "music"]


# --- Create ---------------------------------------------------------------------


def test_create_returns_201_with_filament(filament):
    assert filament["title"] == "Album cover ideas"
    assert filament["source"] == "claude"
    assert filament["tags"] == ["design", "music"]
    assert filament["created_at"] and filament["updated_at"]
    assert "deleted_at" not in filament
    assert Filament.objects.filter(pk=filament["id"]).exists()


def test_create_reuses_existing_tag(client):
    Tag.objects.create(name="music")

    send(client, "post", URL, {**CAPTURE, "tags": ["Music"]})

    assert Tag.objects.filter(name="music").count() == 1


def test_create_ignores_source(client):
    response = send(client, "post", URL, {**CAPTURE, "source": "web"})

    assert response.json()["source"] == "claude"


def test_create_with_nine_tags_rejected(client):
    response = send(client, "post", URL, {**CAPTURE, "tags": [f"t{i}" for i in range(9)]})

    assert response.status_code == 422
    assert errors(response) == [("tags", "Tag limit is 8; got 9")]
    assert Filament.all_objects.count() == 0
    assert Tag.objects.count() == 0


def test_create_with_blank_body_rejected(client):
    response = send(client, "post", URL, {**CAPTURE, "body": "  \n "})

    assert response.status_code == 422
    assert [loc for loc, _ in errors(response)] == ["body"]
    assert Filament.all_objects.count() == 0


# --- Get ------------------------------------------------------------------------


def test_get_returns_filament(client, filament):
    response = client.get(f"{URL}/{filament['id']}")

    assert response.status_code == 200
    assert response.json() == filament


# --- Update ---------------------------------------------------------------------


def test_patch_replaces_tags(client, filament):
    response = send(client, "patch", f"{URL}/{filament['id']}", {"tags": ["Art"]})

    assert response.json()["tags"] == ["art"]


def test_patch_with_empty_tags_clears(client, filament):
    response = send(client, "patch", f"{URL}/{filament['id']}", {"tags": []})

    assert response.json()["tags"] == []


def test_tags_only_patch_moves_updated_at(client, filament):
    response = send(client, "patch", f"{URL}/{filament['id']}", {"tags": ["music"]})

    assert response.json()["updated_at"] > filament["updated_at"]


def test_empty_patch_rejected(client, filament):
    response = send(client, "patch", f"{URL}/{filament['id']}", {})

    assert response.status_code == 422
    assert [msg for _, msg in errors(response)] == ["Send at least one of title, body or tags"]


def test_patch_with_nine_tags_rejected_and_unchanged(client, filament):
    response = send(
        client, "patch", f"{URL}/{filament['id']}", {"tags": [f"t{i}" for i in range(9)]}
    )

    assert response.status_code == 422
    assert client.get(f"{URL}/{filament['id']}").json()["tags"] == ["design", "music"]


# --- Delete ---------------------------------------------------------------------


def test_delete_returns_filament_then_get_is_404(client, filament):
    response = client.delete(f"{URL}/{filament['id']}")

    assert response.status_code == 200
    assert response.json()["title"] == "Album cover ideas"
    assert client.get(f"{URL}/{filament['id']}").json() == NOT_FOUND
    assert Filament.all_objects.get(pk=filament["id"]).deleted_at is not None


def test_delete_twice_is_404(client, filament):
    client.delete(f"{URL}/{filament['id']}")

    response = client.delete(f"{URL}/{filament['id']}")

    assert response.status_code == 404
    assert response.json() == NOT_FOUND


# --- 404s -----------------------------------------------------------------------


@pytest.mark.parametrize("method", ["get", "patch", "delete"])
def test_soft_deleted_filament_is_404_on_every_route(client, filament, method):
    Filament.objects.get(pk=filament["id"]).soft_delete()

    response = send(client, method, f"{URL}/{filament['id']}", {"title": "x"})

    assert response.status_code == 404
    assert response.json() == NOT_FOUND


@pytest.mark.parametrize(
    "filament_id", ["not-a-uuid", "00000000-0000-0000-0000-000000000000"], ids=["bad", "unknown"]
)
def test_missing_or_malformed_id_is_json_404(client, filament_id):
    response = client.get(f"{URL}/{filament_id}")

    assert response.status_code == 404
    assert response["Content-Type"] == "application/json; charset=utf-8"
    assert response.json() == NOT_FOUND


# --- Unexpected errors ----------------------------------------------------------


def test_unexpected_error_returns_generic_json_500(client, monkeypatch, caplog):
    def boom(*args, **kwargs):
        raise RuntimeError("secret internal detail")

    monkeypatch.setattr(services, "create_filament", boom)

    with caplog.at_level(logging.ERROR):
        response = send(client, "post", URL, CAPTURE)

    assert response.status_code == 500
    assert response.json() == {"detail": "Something went wrong on the server. It has been logged."}
    assert "secret internal detail" not in response.text
    assert "secret internal detail" in caplog.text
    assert "Traceback" in caplog.text


# --- Timestamps -----------------------------------------------------------------


def test_timestamps_returned_in_home_timezone(client, filament, settings):
    settings.TIME_ZONE = "America/Chicago"
    stored = dt.datetime(2026, 11, 22, 17, 53, 10, tzinfo=dt.UTC)
    Filament.objects.filter(pk=filament["id"]).update(created_at=stored)

    created_at = client.get(f"{URL}/{filament['id']}").json()["created_at"]

    assert created_at.startswith("2026-11-22T11:53:10")
    assert created_at.endswith("-06:00")
    assert dt.datetime.fromisoformat(created_at) == stored
