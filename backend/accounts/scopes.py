"""Each OAuth client may only ever get its own scope.

DOT's default lets any client request any configured scope, so Claude's client could
ask for `introspection` and inspect other tokens.
"""

from oauth2_provider.scopes import SettingsScopes

from accounts.clients import SCOPE_BY_CLIENT


class PerClientScopes(SettingsScopes):
    def get_available_scopes(self, application=None, request=None, *args, **kwargs):
        if application is None:  # e.g. the metadata document: list them all
            return super().get_available_scopes(application, request, *args, **kwargs)
        scope = SCOPE_BY_CLIENT.get(application.name)
        return [scope] if scope else []

    def get_default_scopes(self, application=None, request=None, *args, **kwargs):
        if application is None:
            return super().get_default_scopes(application, request, *args, **kwargs)
        return self.get_available_scopes(application, request, *args, **kwargs)
