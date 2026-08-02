from datetime import datetime

from django.conf import settings
from django.core.mail import send_mail

from config.celery_app import app as celery_app
from yoolink.users.models import User


@celery_app.task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={"max_retries": 3})
def send_login_2fa_email(self, recipient_email, recipient_name, code, expires_at):
    """Send the CMS login verification code asynchronously."""
    expires_at_label = expires_at

    try:
        expires_at_dt = datetime.fromisoformat(expires_at)
        expires_at_label = expires_at_dt.strftime("%d.%m.%Y %H:%M")
    except (TypeError, ValueError):
        pass

    subject = "Dein Yoolink Sicherheitscode"
    message = (
        f"Hallo {recipient_name},\n\n"
        f"dein Login Sicherheitscode lautet {code}.\n"
        f"Der Code ist bis {expires_at_label} gültig.\n\n"
        "Wenn du diese Anmeldung nicht gestartet hast, ignoriere diese E-Mail."
    )

    from_email = getattr(settings, "DEFAULT_FROM_EMAIL", None) or settings.EMAIL_HOST_USER

    send_mail(
        subject,
        message,
        from_email,
        [recipient_email],
        fail_silently=False,
    )


@celery_app.task(bind=True, autoretry_for=(), time_limit=60 * 60, soft_time_limit=50 * 60)
def create_remote_recovery_backup(self, trigger="scheduled", user_id=None, record_id=None):
    """Create an encrypted private recovery backup in the configured remote storage."""
    from yoolink.ycms.recovery import create_remote_backup

    user = None
    if user_id:
        user = User.objects.filter(id=user_id).first()
    return create_remote_backup(trigger=trigger, user=user, record_id=record_id)
