"""Sign-in page lockout: see the openspec oauth-server spec."""

import datetime as dt
import logging

import pytest
from django.contrib.auth import get_user_model

from accounts.models import LoginThrottle
from accounts.throttle import LOCKED_MESSAGE, LOCKOUT, MAX_FAILURES

pytestmark = pytest.mark.django_db

URL = "/accounts/login/"
PASSWORD = "correct horse battery staple"
IP = "203.0.113.7"


@pytest.fixture
def user():
    return get_user_model().objects.create_user(username="ross", password=PASSWORD)


def attempt(client, password, ip=IP):
    return client.post(URL, {"username": "ross", "password": password}, REMOTE_ADDR=ip)


def fail(client, times, ip=IP):
    for _ in range(times):
        assert attempt(client, "wrong", ip).status_code == 200


def test_correct_password_signs_in(anon_client, user):
    response = attempt(anon_client, PASSWORD)

    assert response.status_code == 302
    assert "_auth_user_id" in anon_client.session


def test_tenth_failure_locks_even_the_correct_password(anon_client, user):
    fail(anon_client, MAX_FAILURES)

    response = attempt(anon_client, PASSWORD)

    assert response.status_code == 429
    assert LOCKED_MESSAGE in response.text
    assert "_auth_user_id" not in anon_client.session


def test_ninth_failure_does_not_lock(anon_client, user):
    fail(anon_client, MAX_FAILURES - 1)

    assert attempt(anon_client, PASSWORD).status_code == 302


def test_lockout_expires_five_minutes_after_the_last_failure(anon_client, user):
    fail(anon_client, MAX_FAILURES)
    row = LoginThrottle.objects.get(ip=IP)
    row.last_failure -= LOCKOUT + dt.timedelta(seconds=1)
    row.save()

    assert attempt(anon_client, PASSWORD).status_code == 302


def test_other_addresses_are_unaffected(anon_client, user):
    fail(anon_client, MAX_FAILURES)

    assert attempt(anon_client, PASSWORD, ip="198.51.100.9").status_code == 302


def test_success_clears_the_count(anon_client, client, user):
    fail(anon_client, MAX_FAILURES - 1)
    assert attempt(anon_client, PASSWORD).status_code == 302

    assert not LoginThrottle.objects.filter(ip=IP).exists()


def test_stale_failures_start_a_new_count(anon_client, user):
    fail(anon_client, MAX_FAILURES - 1)
    LoginThrottle.objects.filter(ip=IP).update(last_failure=dt.datetime(2026, 1, 1, tzinfo=dt.UTC))

    fail(anon_client, 1)

    assert LoginThrottle.objects.get(ip=IP).failures == 1


def test_guessing_while_locked_keeps_it_locked(anon_client, user):
    fail(anon_client, MAX_FAILURES)
    almost_expired = (
        LoginThrottle.objects.get(ip=IP).last_failure - LOCKOUT + dt.timedelta(seconds=5)
    )
    LoginThrottle.objects.filter(ip=IP).update(last_failure=almost_expired)

    assert attempt(anon_client, "wrong").status_code == 429  # restarts the 5 minutes
    LoginThrottle.objects.filter(ip=IP).update(
        last_failure=LoginThrottle.objects.get(ip=IP).last_failure - dt.timedelta(seconds=10)
    )

    assert attempt(anon_client, PASSWORD).status_code == 429


def test_attempt_is_counted_before_the_password_is_checked(anon_client, user, monkeypatch):
    # Parallel requests can't all slip through: each is counted before its slow check.
    import django.contrib.auth.forms as auth_forms

    seen = []
    real_authenticate = auth_forms.authenticate

    def spying_authenticate(*args, **kwargs):
        seen.append(LoginThrottle.objects.get(ip=IP).failures)
        return real_authenticate(*args, **kwargs)

    monkeypatch.setattr(auth_forms, "authenticate", spying_authenticate)
    fail(anon_client, 3)

    assert seen == [1, 2, 3]


def test_missing_remote_addr_does_not_crash(anon_client, user):
    response = attempt(anon_client, "wrong", ip="")

    assert response.status_code == 200


def test_direct_sign_in_lands_on_a_page_the_edge_allows(anon_client, user):
    # The admin is never public, so landing there through the tunnel would be a 404.
    response = attempt(anon_client, PASSWORD)

    assert response["Location"] == "/accounts/signed-in/"
    assert "You're signed in" in anon_client.get("/accounts/signed-in/").text


def test_signed_in_page_needs_a_session(anon_client):
    response = anon_client.get("/accounts/signed-in/")

    assert response.status_code == 302
    assert response["Location"].startswith("/accounts/login/")


def test_password_is_never_logged(anon_client, user, caplog):
    with caplog.at_level(logging.WARNING):
        fail(anon_client, MAX_FAILURES)
        attempt(anon_client, PASSWORD)

    assert "Sign-in failed: ip=203.0.113.7 username='ross'" in caplog.text
    assert "Sign-in refused (locked out)" in caplog.text
    assert "wrong" not in caplog.text
    assert PASSWORD not in caplog.text


def test_login_page_renders_for_phones(anon_client):
    page = anon_client.get(URL).text

    assert 'name="viewport"' in page
    assert 'autocomplete="current-password"' in page
