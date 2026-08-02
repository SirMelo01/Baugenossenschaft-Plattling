import hashlib

from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import (
    PasswordChangeDoneView,
    PasswordChangeView,
    PasswordResetCompleteView,
    PasswordResetConfirmView,
    PasswordResetDoneView,
)
from django.core.cache import cache
from django.urls import reverse_lazy
from django.views.generic.edit import FormView

from .forms import (
    CMSPasswordChangeForm,
    CMSSetPasswordForm,
    UsernameOrEmailPasswordResetForm,
)


class CMSPasswordChangeView(LoginRequiredMixin, PasswordChangeView):
    form_class = CMSPasswordChangeForm
    template_name = "pages/cms/auth/password_change.html"
    success_url = reverse_lazy("ycms:password_change_done")

    def form_valid(self, form):
        response = super().form_valid(form)
        if hasattr(self.request.user, "usersettings"):
            settings_obj = self.request.user.usersettings
            if settings_obj.must_change_password:
                settings_obj.must_change_password = False
                settings_obj.save(update_fields=["must_change_password"])
        return response


class CMSPasswordChangeDoneView(LoginRequiredMixin, PasswordChangeDoneView):
    template_name = "pages/cms/auth/password_change_done.html"


class CMSPasswordResetRequestView(FormView):
    form_class = UsernameOrEmailPasswordResetForm
    template_name = "pages/cms/auth/password_reset_request.html"
    success_url = reverse_lazy("ycms:password_reset_done")

    def _is_rate_limited(self, raw_login: str) -> bool:
        ip = self.request.META.get("REMOTE_ADDR", "unknown")
        normalized_login = raw_login.strip().lower()
        login_hash = hashlib.sha256(normalized_login.encode("utf-8")).hexdigest()

        key = f"ycms:password-reset:{ip}:{login_hash}"
        attempts = cache.get(key, 0)

        if attempts >= 5:
            return True

        cache.set(key, attempts + 1, timeout=900)
        return False

    def form_valid(self, form):
        raw_login = form.cleaned_data["login"]

        if not self._is_rate_limited(raw_login):
            form.save(
                request=self.request,
                use_https=self.request.is_secure(),
                from_email=getattr(settings, "DEFAULT_FROM_EMAIL", settings.EMAIL_HOST_USER),
            )

        return super().form_valid(form)


class CMSPasswordResetDoneView(PasswordResetDoneView):
    template_name = "pages/cms/auth/password_reset_done.html"


class CMSPasswordResetConfirmView(PasswordResetConfirmView):
    form_class = CMSSetPasswordForm
    template_name = "pages/cms/auth/password_reset_confirm.html"
    success_url = reverse_lazy("ycms:password_reset_complete")

    def form_valid(self, form):
        response = super().form_valid(form)
        user = form.user
        if hasattr(user, "usersettings"):
            settings_obj = user.usersettings
            if settings_obj.must_change_password:
                settings_obj.must_change_password = False
                settings_obj.save(update_fields=["must_change_password"])
        return response


class CMSPasswordResetCompleteView(PasswordResetCompleteView):
    template_name = "pages/cms/auth/password_reset_complete.html"
