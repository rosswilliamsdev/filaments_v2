"""Home timezone: see the openspec filament-storage spec."""

import datetime as dt

import pytest
from django.core.exceptions import ImproperlyConfigured
from django.utils import timezone

from config.settings import env_timezone
from filaments.models import Filament


@pytest.mark.django_db
def test_late_evening_note_counts_as_local_day(settings):
    settings.TIME_ZONE = "America/Chicago"
    filament = Filament.objects.create(title="Late idea", body="Before bed", source="claude")
    # 23:30 on Nov 24 in Chicago is 05:30 UTC on Nov 25.
    utc_moment = dt.datetime(2026, 11, 25, 5, 30, tzinfo=dt.UTC)
    Filament.objects.filter(pk=filament.pk).update(created_at=utc_moment)

    filament.refresh_from_db()

    assert filament.created_at == utc_moment
    assert filament.created_at.utcoffset() == dt.timedelta(0)  # stored and read back as UTC
    assert timezone.localtime(filament.created_at).date() == dt.date(2026, 11, 24)


def test_timezone_setting_is_read_and_defaults_to_utc(monkeypatch):
    monkeypatch.setenv("FILAMENTS_TIMEZONE", "America/Chicago")
    assert env_timezone("FILAMENTS_TIMEZONE") == "America/Chicago"

    monkeypatch.delenv("FILAMENTS_TIMEZONE")
    assert env_timezone("FILAMENTS_TIMEZONE") == "UTC"


@pytest.mark.parametrize("name", ["America/Chicagoo", "../etc/passwd"])
def test_unknown_timezone_fails_startup(monkeypatch, name):
    monkeypatch.setenv("FILAMENTS_TIMEZONE", name)

    with pytest.raises(ImproperlyConfigured, match="FILAMENTS_TIMEZONE"):
        env_timezone("FILAMENTS_TIMEZONE")
