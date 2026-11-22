"""Django behind Cloudflare and the edge proxy: see the openspec remote-access and
oauth-server specs."""

import pytest
from django.contrib.auth import get_user_model
from django.test import Client

from accounts.models import LoginThrottle
from accounts.throttle import MAX_FAILURES
from config.settings import public_url_settings

PASSWORD = "correct horse battery staple"


def test_public_url_settings_for_the_tunnel():
    values = public_url_settings("https://myfilaments.dev")

    assert values["host"] == "myfilaments.dev"
    assert values["origin"] == "https://myfilaments.dev"
    assert values["SECURE_PROXY_SSL_HEADER"] == ("HTTP_X_FORWARDED_PROTO", "https")
    assert values["SESSION_COOKIE_SECURE"] is True
    assert values["CSRF_COOKIE_SECURE"] is True


def test_public_url_settings_for_local_http():
    values = public_url_settings("http://127.0.0.1:8080")

    assert values["origin"] == "http://127.0.0.1:8080"
    assert values["SESSION_COOKIE_SECURE"] is False
    # Plain-http site: a forwarded "https" header must not make Django think otherwise.
    assert values["SECURE_PROXY_SSL_HEADER"] is None


def test_public_url_with_a_path_is_refused(monkeypatch):
    from django.core.exceptions import ImproperlyConfigured

    from config.settings import env_url

    monkeypatch.setenv("FILAMENTS_PUBLIC_URL", "https://myfilaments.dev/notes")

    with pytest.raises(ImproperlyConfigured, match="without a path"):
        env_url("FILAMENTS_PUBLIC_URL", "http://127.0.0.1:8000")


@pytest.mark.django_db
def test_sign_in_through_the_tunnel(settings):
    # What a request looks like at Django after Cloudflare -> cloudflared -> edge.
    public = public_url_settings("https://myfilaments.dev")
    settings.ALLOWED_HOSTS = [*settings.ALLOWED_HOSTS, public["host"]]
    settings.CSRF_TRUSTED_ORIGINS = [public["origin"]]
    settings.SESSION_COOKIE_SECURE = True
    settings.SECURE_PROXY_SSL_HEADER = public["SECURE_PROXY_SSL_HEADER"]
    get_user_model().objects.create_user("ross", password=PASSWORD)
    browser = Client(enforce_csrf_checks=True)
    forwarded = {
        "HTTP_HOST": "myfilaments.dev",
        "HTTP_X_FORWARDED_PROTO": "https",
        "HTTP_ORIGIN": "https://myfilaments.dev",
        "HTTP_REFERER": "https://myfilaments.dev/accounts/login/",
    }
    page = browser.get("/accounts/login/", **forwarded)
    csrf = page.cookies["csrftoken"].value

    response = browser.post(
        "/accounts/login/",
        {"username": "ross", "password": PASSWORD, "csrfmiddlewaretoken": csrf},
        **forwarded,
    )

    assert response.status_code == 302
    assert response.wsgi_request.is_secure()
    assert response.cookies["sessionid"]["secure"] is True


@pytest.mark.django_db
def test_lockout_counts_each_tunnel_visitor_separately(anon_client):
    get_user_model().objects.create_user("ross", password=PASSWORD)

    def attempt(password, visitor):
        return anon_client.post(
            "/accounts/login/",
            {"username": "ross", "password": password},
            REMOTE_ADDR="172.18.0.4",  # every tunnel request arrives from the edge
            HTTP_CF_CONNECTING_IP=visitor,
        )

    for _ in range(MAX_FAILURES):
        attempt("wrong", "203.0.113.7")

    assert attempt(PASSWORD, "203.0.113.7").status_code == 429
    assert attempt(PASSWORD, "198.51.100.9").status_code == 302
    assert not LoginThrottle.objects.filter(ip="172.18.0.4").exists()


@pytest.mark.django_db
def test_local_request_uses_the_connection_address(anon_client):
    anon_client.post(
        "/accounts/login/", {"username": "x", "password": "y"}, REMOTE_ADDR="127.0.0.1"
    )

    assert LoginThrottle.objects.get().ip == "127.0.0.1"


@pytest.mark.django_db
def test_garbage_cf_header_falls_back_to_the_connection_address(anon_client):
    anon_client.post(
        "/accounts/login/",
        {"username": "x", "password": "y"},
        REMOTE_ADDR="127.0.0.1",
        HTTP_CF_CONNECTING_IP="not-an-ip; DROP TABLE",
    )

    assert LoginThrottle.objects.get().ip == "127.0.0.1"


def test_docker_service_name_is_an_allowed_host(settings):
    # The mcp container reaches Django at http://web:8000 (API and introspection).
    from django.conf import settings as live

    assert "web" in live.ALLOWED_HOSTS
