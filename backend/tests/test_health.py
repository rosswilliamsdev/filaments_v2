"""GET /api/health — see openspec api-health spec."""

from unittest import mock

import pytest
from django.db import OperationalError

pytestmark = pytest.mark.django_db


def test_health_ok(client):
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_needs_no_credentials(client):
    response = client.get("/api/health", headers={})

    assert "HTTP_AUTHORIZATION" not in response.wsgi_request.META
    assert response.status_code == 200


def test_health_database_unavailable(client, caplog):
    with mock.patch(
        "api.health.connection.cursor",
        side_effect=OperationalError("connection refused"),
    ):
        response = client.get("/api/health")

    assert response.status_code == 503
    assert response.json() == {"detail": "Database unavailable"}
    # The error goes to the log, never into the response body.
    assert "connection refused" not in response.content.decode()
    assert "Health check failed" in caplog.text
