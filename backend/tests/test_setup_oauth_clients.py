"""`manage.py setup_oauth_clients`: see the openspec oauth-server spec."""

import re
from io import StringIO

import pytest
from django.contrib.auth import get_user_model
from django.core.management import CommandError, call_command
from oauth2_provider.models import get_application_model

from accounts.clients import CLAUDE, CLAUDE_REDIRECT_URI, MCP_INTROSPECTION

pytestmark = pytest.mark.django_db
Application = get_application_model()


@pytest.fixture
def owner():
    return get_user_model().objects.create_superuser("ross", password="pw")


def run(*args) -> str:
    out = StringIO()
    call_command("setup_oauth_clients", *args, stdout=out)
    return out.getvalue()


def secrets(output: str) -> list[str]:
    return re.findall(r"Client secret: (\S+)", output)


def test_first_run_creates_both_clients_and_prints_secrets(owner):
    output = run()

    claude = Application.objects.get(name=CLAUDE)
    mcp = Application.objects.get(name=MCP_INTROSPECTION)
    assert claude.redirect_uris == CLAUDE_REDIRECT_URI
    assert claude.authorization_grant_type == Application.GRANT_AUTHORIZATION_CODE
    assert claude.skip_authorization is True
    assert mcp.authorization_grant_type == Application.GRANT_CLIENT_CREDENTIALS
    printed = secrets(output)
    assert len(printed) == 2
    # Stored hashed, so the printed secret is not what the database holds. That the
    # printed secrets work is proven in test_oauth.py.
    assert claude.client_secret not in printed


def test_rerun_changes_nothing(owner):
    run()
    before = {a.name: a.client_secret for a in Application.objects.all()}

    output = run()

    assert secrets(output) == []
    assert {a.name: a.client_secret for a in Application.objects.all()} == before
    assert Application.objects.count() == 2


def test_rotate_issues_new_secrets(owner):
    run()
    before = {a.name: a.client_secret for a in Application.objects.all()}

    output = run("--rotate")

    assert len(secrets(output)) == 2
    after = {a.name: a.client_secret for a in Application.objects.all()}
    assert all(after[name] != before[name] for name in before)
    assert Application.objects.count() == 2


def test_refuses_without_an_account():
    with pytest.raises(CommandError, match="createsuperuser"):
        run()
