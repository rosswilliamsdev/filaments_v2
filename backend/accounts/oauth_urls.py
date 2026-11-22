"""The OAuth routes Filaments publishes, and nothing more.

DOT's own `urlpatterns` would also publish application management, the device flow and
OIDC routes. Mounted at the root because RFC 8414 metadata lives at the origin's
/.well-known/. The namespace must be `oauth2_provider`: DOT's views reverse names in it.
"""

from django.urls import path
from oauth2_provider import views
from oauth2_provider.urls import metadata_urlpatterns

from accounts.introspection import McpIntrospectTokenView

app_name = "oauth2_provider"

urlpatterns = [
    *metadata_urlpatterns,
    path("o/authorize/", views.AuthorizationView.as_view(), name="authorize"),
    path("o/token/", views.TokenView.as_view(), name="token"),
    path("o/revoke_token/", views.RevokeTokenView.as_view(), name="revoke-token"),
    path("o/introspect/", McpIntrospectTokenView.as_view(), name="introspect"),
]
