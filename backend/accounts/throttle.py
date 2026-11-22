"""Sign-in lockout: 10 failures from one IP address lock it out for 5 minutes.

Per address, not global: a global lockout would let anyone lock out the only user.
Every attempt is counted *before* the password is checked, under a row lock, so
parallel requests can't slip extra guesses past the limit. While locked, each further
attempt restarts the 5 minutes. A successful sign-in clears the address.
"""

import datetime as dt
import ipaddress

from django.db import transaction
from django.utils import timezone

from accounts.models import LoginThrottle

MAX_FAILURES = 10
LOCKOUT = dt.timedelta(minutes=5)
LOCKED_MESSAGE = "Too many failed sign-ins. Try again in a few minutes."
UNKNOWN_IP = "0.0.0.0"  # REMOTE_ADDR can be empty (e.g. a unix socket); share one bucket


def _valid_ip(value: str | None) -> str | None:
    try:
        return str(ipaddress.ip_address((value or "").strip()))
    except ValueError:
        return None


def client_ip(request) -> str:
    """The visitor's address.

    Through the tunnel every request reaches Django from the edge proxy, so the real
    visitor is in CF-Connecting-IP. Trusting it is safe: Cloudflare overwrites it on all
    public traffic, and the only other way to reach Django is 127.0.0.1 on the laptop.
    """
    return (
        _valid_ip(request.META.get("HTTP_CF_CONNECTING_IP"))
        or _valid_ip(request.META.get("REMOTE_ADDR"))
        or UNKNOWN_IP
    )


def reserve_attempt(ip: str) -> int | None:
    """Count a sign-in attempt before checking the password.

    Returns the address's attempt count, or None when the address is locked out (the
    attempt is refused and the lockout restarts).
    """
    now = timezone.now()
    with transaction.atomic():
        # Row lock: concurrent attempts from one address are counted one at a time.
        row, _ = LoginThrottle.objects.select_for_update().get_or_create(
            ip=ip, defaults={"failures": 0, "last_failure": now}
        )
        recent = now - row.last_failure < LOCKOUT
        if row.failures >= MAX_FAILURES and recent:
            row.last_failure = now  # guessing while locked keeps it locked
            row.save(update_fields=["last_failure"])
            return None
        if not recent:
            row.failures = 0  # the previous run of failures has gone stale
        row.failures += 1
        row.last_failure = now
        row.save(update_fields=["failures", "last_failure"])
        return row.failures


def clear(ip: str) -> None:
    LoginThrottle.objects.filter(ip=ip).delete()
