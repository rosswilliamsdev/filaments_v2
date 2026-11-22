from django.db import models


class LoginThrottle(models.Model):
    """Failed sign-ins per IP address (see accounts.throttle).

    A table rather than a cache: gunicorn's workers each have their own memory, and
    the lockout must count attempts across all of them.
    """

    ip = models.GenericIPAddressField(unique=True)
    failures = models.PositiveIntegerField(default=0)
    last_failure = models.DateTimeField()

    def __str__(self) -> str:
        return f"{self.ip}: {self.failures} failures"
