from django import forms
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import PasswordChangeForm, SetPasswordForm
from django.contrib.auth.tokens import default_token_generator
from django.contrib.sites.shortcuts import get_current_site
from django.core.mail import send_mail
from django.db.models import Q
from django.template.loader import render_to_string
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from .models import fileentry, Blog, UserSettings


class MultipleClearableFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    def clean(self, data, initial=None):
        single_file_clean = super().clean
        if isinstance(data, (list, tuple)):
            return [single_file_clean(file, initial) for file in data]
        return [single_file_clean(data, initial)]


class fileform(forms.ModelForm):
    label = ""
    file = MultipleFileField(widget=MultipleClearableFileInput)

    class Meta:
        model = fileentry
        fields = ("file",)


class Blogform(forms.ModelForm):
    label = ""

    class Meta:
        model = Blog
        fields = "__all__"


User = get_user_model()

INPUT_CLASSES = (
    "w-full text-lg py-3 px-4 border border-gray-300 rounded-2xl "
    "focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
)


class TailwindAuthFormMixin:
    def apply_base_styles(self):
        for field in self.fields.values():
            css_class = field.widget.attrs.get("class", "")
            field.widget.attrs["class"] = f"{css_class} {INPUT_CLASSES}".strip()


class CMSPasswordChangeForm(TailwindAuthFormMixin, PasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["old_password"].label = "Altes Passwort"
        self.fields["new_password1"].label = "Neues Passwort"
        self.fields["new_password2"].label = "Neues Passwort wiederholen"

        self.fields["old_password"].widget.attrs.update(
            {
                "placeholder": "Altes Passwort eingeben",
                "autocomplete": "current-password",
            }
        )
        self.fields["new_password1"].widget.attrs.update(
            {
                "placeholder": "Neues Passwort eingeben",
                "autocomplete": "new-password",
            }
        )
        self.fields["new_password2"].widget.attrs.update(
            {
                "placeholder": "Neues Passwort wiederholen",
                "autocomplete": "new-password",
            }
        )

        self.apply_base_styles()


class CMSSetPasswordForm(TailwindAuthFormMixin, SetPasswordForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["new_password1"].label = "Neues Passwort"
        self.fields["new_password2"].label = "Neues Passwort wiederholen"

        self.fields["new_password1"].widget.attrs.update(
            {
                "placeholder": "Neues Passwort eingeben",
                "autocomplete": "new-password",
            }
        )
        self.fields["new_password2"].widget.attrs.update(
            {
                "placeholder": "Neues Passwort wiederholen",
                "autocomplete": "new-password",
            }
        )

        self.apply_base_styles()


class UsernameOrEmailPasswordResetForm(forms.Form):
    login = forms.CharField(
        label="Benutzername oder E-Mail",
        max_length=254,
        widget=forms.TextInput(
            attrs={
                "class": INPUT_CLASSES,
                "placeholder": "Benutzername oder E-Mail eingeben",
                "autocomplete": "username",
            }
        ),
    )

    def _get_email_for_user(self, user):
        user_settings = UserSettings.objects.filter(user=user).only("email").first()

        if user_settings and user_settings.email and user_settings.email.strip():
            return user_settings.email.strip()

        return (user.email or "").strip()

    def _get_users_for_login(self, login: str):
        login = login.strip()

        if "@" in login:
            return User._default_manager.filter(
                Q(is_active=True),
                Q(usersettings__email__iexact=login) | Q(email__iexact=login),
            ).distinct()

        return User._default_manager.filter(
            is_active=True,
            username__iexact=login,
        )

    def save(
        self,
        request,
        use_https=False,
        token_generator=default_token_generator,
        from_email=None,
        subject_template_name="pages/cms/auth/password_reset_subject.txt",
        email_template_name="pages/cms/auth/password_reset_email.txt",
    ):
        login = self.cleaned_data["login"].strip()
        current_site = get_current_site(request)
        from_email = from_email or getattr(
            settings, "DEFAULT_FROM_EMAIL", settings.EMAIL_HOST_USER
        )

        for user in self._get_users_for_login(login):
            if not user.has_usable_password():
                continue

            recipient_email = self._get_email_for_user(user)

            if not recipient_email:
                continue

            context = {
                "email": recipient_email,
                "domain": current_site.domain,
                "site_name": current_site.name,
                "uid": urlsafe_base64_encode(force_bytes(user.pk)),
                "user": user,
                "token": token_generator.make_token(user),
                "protocol": "https" if use_https else "http",
            }

            subject = render_to_string(subject_template_name, context)
            subject = "".join(subject.splitlines())

            message = render_to_string(email_template_name, context)

            send_mail(
                subject=subject,
                message=message,
                from_email=from_email,
                recipient_list=[recipient_email],
                fail_silently=False,
            )
