"""Service-token auth on the API: see the openspec api-auth spec."""

import json
import logging

import pytest

from filaments.models import Filament

pytestmark = pytest.mark.django_db

UNAUTHORIZED = {"detail": "Missing or invalid API token"}
SOME_ID = "00000000-0000-0000-0000-000000000000"
BODY = json.dumps({"title": "Album cover ideas", "body": "Matte sleeve"})

# Every non-health route, as (method, path, json body or None).
ROUTES = [
    ("get", "/api/filaments", None),
    ("post", "/api/filaments", BODY),
    ("get", f"/api/filaments/{SOME_ID}", None),
    ("patch", f"/api/filaments/{SOME_ID}", json.dumps({"title": "x"})),
    ("delete", f"/api/filaments/{SOME_ID}", None),
    ("get", "/api/tags", None),
]


def call(client, method, path, body, **headers):
    kwargs = {"headers": headers}
    if body is not None:
        kwargs |= {"data": body, "content_type": "application/json"}
    return getattr(client, method)(path, **kwargs)


@pytest.mark.parametrize(("method", "path", "body"), ROUTES, ids=lambda r: str(r)[:30])
def test_every_route_rejects_a_missing_token(anon_client, method, path, body):
    response = call(anon_client, method, path, body)

    assert response.status_code == 401
    assert response.json() == UNAUTHORIZED


def test_rejected_create_stores_nothing(anon_client):
    call(anon_client, "post", "/api/filaments", BODY)

    assert Filament.all_objects.count() == 0


@pytest.mark.parametrize(
    "authorization",
    ["Bearer wrong-token-" + "y" * 30, "Token {token}", "Basic {token}", "Bearer", "{token}"],
    ids=["wrong-token", "token-scheme", "basic-scheme", "no-token", "no-scheme"],
)
def test_bad_credentials_are_rejected(anon_client, api_token, authorization):
    header = authorization.format(token=api_token)

    response = anon_client.get("/api/filaments", headers={"Authorization": header})

    assert response.status_code == 401
    assert response.json() == UNAUTHORIZED


def test_non_ascii_token_is_a_401_not_a_500(anon_client):
    response = anon_client.get("/api/filaments", headers={"Authorization": "Bearer café"})

    assert response.status_code == 401


def test_correct_token_is_accepted(client):
    assert client.get("/api/filaments").status_code == 200
    assert call(client, "post", "/api/filaments", BODY).status_code == 201


def test_health_needs_no_token(anon_client):
    assert anon_client.get("/api/health").status_code == 200


def test_rejection_is_logged_without_tokens(anon_client, api_token, caplog):
    presented = "wrong-token-" + "z" * 30

    with caplog.at_level(logging.WARNING):
        anon_client.get("/api/tags", headers={"Authorization": f"Bearer {presented}"})

    assert "Rejected API request: GET /api/tags" in caplog.text
    assert presented not in caplog.text
    assert api_token not in caplog.text
