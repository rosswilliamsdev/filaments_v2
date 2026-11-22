from django.contrib import admin
from django.contrib.auth.views import LogoutView
from django.urls import include, path

from accounts.views import ThrottledLoginView
from api.api import api

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", api.urls),
    path("accounts/login/", ThrottledLoginView.as_view(), name="login"),
    path("accounts/logout/", LogoutView.as_view(), name="logout"),
    # /.well-known/oauth-authorization-server and /o/{authorize,token,revoke_token,introspect}/
    path("", include("accounts.oauth_urls")),
]
