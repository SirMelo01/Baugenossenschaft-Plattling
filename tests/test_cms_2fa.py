import pytest
from django.conf import settings
from django.contrib import auth
from django.contrib.sites.models import Site
from django.core import mail
from django.test import Client
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta

from yoolink.users.tests.factories import UserFactory
from yoolink.ycms.models import UserSettings
from yoolink.ycms.tasks import send_login_2fa_email

pytestmark = pytest.mark.django_db


def _create_user_with_settings(*, two_factor_enabled=True, email="user@example.com"):
    user = UserFactory(email=email)
    user.set_password("password12345")
    user.save(update_fields=["password", "email"])

    user_settings = UserSettings.objects.create(
        user=user,
        email=email,
        full_name="Test User",
        two_factor_email_enabled=two_factor_enabled,
        two_factor_email_verified=two_factor_enabled,
    )
    return user, user_settings


def test_login_routes_to_2fa_and_queues_email(monkeypatch):
    user, user_settings = _create_user_with_settings()
    client = Client()
    queued = {}

    def fake_delay(**kwargs):
        queued.update(kwargs)
        return None

    monkeypatch.setattr("yoolink.ycms.views.send_login_2fa_email.delay", fake_delay)

    response = client.post(
        reverse("ycms:login"),
        data={"username": user.username, "password": "password12345"},
    )

    assert response.status_code == 302
    assert response.url == reverse("ycms:login-2fa")

    user_settings.refresh_from_db()
    assert user_settings.two_factor_email_code
    assert user_settings.two_factor_email_code_expires_at is not None
    assert user_settings.two_factor_email_verified is False
    assert queued["recipient_email"] == user.email
    assert queued["recipient_name"] == user_settings.full_name
    assert queued["code"] == user_settings.two_factor_email_code

    session = client.session
    assert session["cms_2fa_user_id"] == user.id
    assert session["cms_2fa_attempts"] == 0


def test_login_2fa_verification_logs_user_in():
    user, user_settings = _create_user_with_settings()
    user_settings.two_factor_email_code = "123456"
    user_settings.two_factor_email_code_expires_at = timezone.now() + timedelta(minutes=10)
    user_settings.save(update_fields=["two_factor_email_code", "two_factor_email_code_expires_at"])

    client = Client()
    session = client.session
    session["cms_2fa_user_id"] = user.id
    session["cms_2fa_backend"] = settings.AUTHENTICATION_BACKENDS[0]
    session["cms_2fa_attempts"] = 0
    session.save()

    response = client.post(reverse("ycms:login-2fa"), data={"code": "123456", "action": "verify"})

    assert response.status_code == 302
    assert response.url == reverse("ycms:cms")

    session = client.session
    assert str(session.get(auth.SESSION_KEY)) == str(user.id)
    assert session.get("cms_2fa_user_id") is None
    assert session.get("cms_2fa_attempts") is None

    user_settings.refresh_from_db()
    assert user_settings.two_factor_email_verified is True
    assert user_settings.two_factor_email_code == ""


def test_login_2fa_locks_session_after_too_many_failed_attempts():
    user, user_settings = _create_user_with_settings()
    user_settings.two_factor_email_code = "123456"
    user_settings.two_factor_email_code_expires_at = timezone.now() + timedelta(minutes=10)
    user_settings.save(update_fields=["two_factor_email_code", "two_factor_email_code_expires_at"])

    client = Client()
    session = client.session
    session["cms_2fa_user_id"] = user.id
    session["cms_2fa_backend"] = settings.AUTHENTICATION_BACKENDS[0]
    session["cms_2fa_attempts"] = 4
    session.save()

    response = client.post(reverse("ycms:login-2fa"), data={"code": "000000", "action": "verify"})

    assert response.status_code == 200
    assert "Zu viele Fehlversuche" in response.content.decode("utf-8")

    session = client.session
    assert session.get("cms_2fa_user_id") is None
    assert session.get("cms_2fa_backend") is None
    assert session.get("cms_2fa_attempts") is None


def test_2fa_mail_task_sends_mail(settings):
    settings.CELERY_TASK_ALWAYS_EAGER = True
    settings.CELERY_TASK_EAGER_PROPAGATES = True

    result = send_login_2fa_email.delay(
        recipient_email="someone@example.com",
        recipient_name="Someone",
        code="654321",
        expires_at="2026-04-27T12:34:00+00:00",
    )

    assert result.result is None
    assert len(mail.outbox) == 1
    assert mail.outbox[0].subject == "Dein Yoolink Sicherheitscode"
    assert "654321" in mail.outbox[0].body


def test_security_settings_endpoints_work_for_logged_in_user(monkeypatch):
    user, user_settings = _create_user_with_settings(two_factor_enabled=False)
    client = Client()
    client.force_login(user)

    security_page = client.get(reverse("ycms:security-settings"))
    assert security_page.status_code == 200

    queued = {}

    def fake_delay(**kwargs):
        queued.update(kwargs)
        return None

    monkeypatch.setattr("yoolink.ycms.views.send_login_2fa_email.delay", fake_delay)

    send_code = client.post(reverse("ycms:security-send-code"))
    assert send_code.status_code == 200
    assert "success" in send_code.json()

    user_settings.refresh_from_db()
    code = user_settings.two_factor_email_code
    assert code
    assert queued["recipient_email"] == user.email

    verify = client.post(reverse("ycms:security-verify-code"), data={"code": code})
    assert verify.status_code == 200
    assert "success" in verify.json()

    user_settings.refresh_from_db()
    assert user_settings.two_factor_email_enabled is True
    assert user_settings.two_factor_email_verified is True

    disable = client.post(reverse("ycms:security-disable-2fa"))
    assert disable.status_code == 200
    assert "success" in disable.json()

    user_settings.refresh_from_db()
    assert user_settings.two_factor_email_enabled is False
    assert user_settings.two_factor_email_verified is False


def test_password_reset_endpoints_and_email_flow_work():
    user, _ = _create_user_with_settings(two_factor_enabled=False)
    Site.objects.update_or_create(
        id=settings.SITE_ID,
        defaults={"domain": "testserver", "name": "testserver"},
    )

    client = Client()

    request_page = client.get(reverse("ycms:password_reset"))
    assert request_page.status_code == 200

    response = client.post(reverse("ycms:password_reset"), data={"login": user.username})
    assert response.status_code == 302
    assert response.url == reverse("ycms:password_reset_done")
    assert len(mail.outbox) >= 1

    done_page = client.get(reverse("ycms:password_reset_done"))
    assert done_page.status_code == 200


def test_login_shows_error_alert_for_invalid_credentials():
    client = Client()

    response = client.post(
        reverse("ycms:login"),
        data={"username": "unknown", "password": "wrong"},
    )

    assert response.status_code == 200
    page = response.content.decode("utf-8")
    assert "Benutzername oder Passwort ist ungültig." in page
    assert "Login fehlgeschlagen" in page
    assert "id=\"loginError\"" in page
    assert "aria-invalid=\"true\"" in page
    assert "sendNotif" in page
    assert "role=\"alert\"" in page


def test_login_shows_error_for_empty_credentials():
    client = Client()

    response = client.post(reverse("ycms:login"), data={"username": "", "password": ""})

    assert response.status_code == 200
    assert "Bitte Nutzername und Passwort eingeben." in response.content.decode("utf-8")
