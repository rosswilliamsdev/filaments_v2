import logging

from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView
from django.views.generic import TemplateView

from accounts import throttle

logger = logging.getLogger(__name__)


class ThrottledLoginView(LoginView):
    """Django's login view with the per-address lockout from accounts.throttle."""

    template_name = "registration/login.html"
    redirect_authenticated_user = True

    def post(self, request, *args, **kwargs):
        ip = throttle.client_ip(request)
        attempts = throttle.reserve_attempt(ip)
        if attempts is None:
            # Refused without checking the password, so a locked address learns nothing.
            logger.warning(
                "Sign-in refused (locked out): ip=%s username=%r", ip, request.POST.get("username")
            )
            context = self.get_context_data(
                form=self.get_form(), locked_message=throttle.LOCKED_MESSAGE
            )
            return self.render_to_response(context, status=429)
        self.attempts = attempts
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        throttle.clear(throttle.client_ip(self.request))
        return super().form_valid(form)

    def form_invalid(self, form):
        # The attempt was already counted in post(). Never log the password.
        logger.warning(
            "Sign-in failed: ip=%s username=%r failures=%d",
            throttle.client_ip(self.request),
            form.data.get("username"),
            self.attempts,
        )
        return super().form_invalid(form)


class SignedInView(LoginRequiredMixin, TemplateView):
    """Where a direct sign-in lands (Claude's sign-ins return to Claude instead)."""

    template_name = "registration/signed_in.html"
