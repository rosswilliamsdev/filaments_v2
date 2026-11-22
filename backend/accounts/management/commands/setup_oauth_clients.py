"""Create the pre-registered OAuth clients and print their secrets once.

Safe to re-run: existing clients are left alone unless --rotate is given.
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from oauth2_provider.generators import generate_client_secret
from oauth2_provider.models import AbstractApplication, get_application_model

from accounts.clients import CLAUDE, CLAUDE_REDIRECT_URI, CLIENTS, MCP_INTROSPECTION


class Command(BaseCommand):
    help = "Create the Claude and MCP-introspection OAuth clients; print new secrets once."

    def add_arguments(self, parser):
        parser.add_argument(
            "--rotate",
            action="store_true",
            help="Issue new secrets for both clients (old secrets stop working).",
        )

    def handle(self, *args, rotate: bool = False, **options):
        owner = get_user_model().objects.filter(is_superuser=True).order_by("pk").first()
        if owner is None:
            raise CommandError("Create your account first: manage.py createsuperuser")

        Application = get_application_model()
        for spec in CLIENTS:
            app = Application.objects.filter(name=spec.name).first()
            if app is not None and not rotate:
                self.stdout.write(f"{spec.name}: exists, unchanged (use --rotate for new secrets)")
                continue
            if app is None:
                app = Application(
                    name=spec.name,
                    user=owner,
                    client_type=AbstractApplication.CLIENT_CONFIDENTIAL,
                    authorization_grant_type=spec.grant_type,
                    redirect_uris=spec.redirect_uris,
                    skip_authorization=spec.skip_authorization,
                )
            secret = generate_client_secret()
            app.client_secret = secret  # hashed on save; this is the only time it's shown
            app.save()
            self._print_client(spec.name, app.client_id, secret)

    def _print_client(self, name: str, client_id: str, secret: str) -> None:
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(f"{name}: new secret issued. It is shown only once."))
        self.stdout.write(f"  Client ID:     {client_id}")
        self.stdout.write(f"  Client secret: {secret}")
        if name == CLAUDE:
            self.stdout.write(
                "  Paste both into claude.ai when adding the connector: choose "
                f'"Use your own OAuth client". Redirect URL: {CLAUDE_REDIRECT_URI}'
            )
        elif name == MCP_INTROSPECTION:
            self.stdout.write(
                "  For the MCP server (step 9): put these in .env as "
                "FILAMENTS_INTROSPECTION_CLIENT_ID and FILAMENTS_INTROSPECTION_CLIENT_SECRET."
            )
