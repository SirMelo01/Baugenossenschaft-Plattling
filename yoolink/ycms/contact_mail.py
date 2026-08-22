"""Versand der Kontaktanfragen per E-Mail.

Jede Anfrage aus einem der drei Kontaktformulare geht an die im CMS unter
Website-Daten hinterlegte Adresse; der Absender bekommt eine kurze Bestaetigung.
Der Betreff traegt die Anfrageart in eckigen Klammern, damit sich die Mails im
Postfach genauso filtern lassen wie die Benachrichtigungen im CMS.

Der Versand darf eine Anfrage nie verlieren: die ``Message`` ist zum Zeitpunkt
des Aufrufs bereits gespeichert und im CMS sichtbar. Schlaegt der Mailversand
fehl (Postfach nicht erreichbar, SMTP falsch konfiguriert), wird das protokolliert
statt eine Fehlerseite zu zeigen.
"""

import logging

from django.conf import settings
from django.core.mail import EmailMessage

from .models import Message, WebsiteSettings, contact_category_meta

logger = logging.getLogger(__name__)

# Anhaenge gehen mit in die interne Mail, damit im Postfach alles beieinander
# liegt. Ueber dieser Summe bleiben sie draussen - viele Postfaecher weisen
# groessere Nachrichten ab, und die Anfrage waere dann ganz verloren. Im CMS
# haengen sie ohnehin an der Anfrage.
MAX_MAIL_ATTACHMENT_BYTES = 8 * 1024 * 1024


def _recipient() -> str:
    """Postfach der Genossenschaft (Website-Daten, sonst der SMTP-Absender)."""
    owner = WebsiteSettings.get_site_owner()
    return (getattr(owner, "contact_email", "") or "").strip() or settings.EMAIL_HOST_USER


def _sender() -> str:
    return getattr(settings, "DEFAULT_FROM_EMAIL", "") or settings.EMAIL_HOST_USER


def _company_name() -> str:
    owner = WebsiteSettings.get_site_owner()
    return (getattr(owner, "company_name", "") or "").strip() or "Baugenossenschaft Plattling eG"


def build_internal_body(message: Message) -> str:
    meta = contact_category_meta(message.category)
    lines = [
        f"Neue Anfrage über das Formular \"{meta['label']}\".",
        "",
        f"Art der Anfrage: {meta['label']}",
        f"Name:            {message.name}",
        f"E-Mail:          {message.email}",
    ]
    if message.phone:
        lines.append(f"Telefon:         {message.phone}")
    if message.title:
        lines.append(f"Betreff:         {message.title}")

    rows = message.detail_rows
    if rows:
        lines.extend(["", "Angaben aus dem Formular:"])
        width = max(len(row["label"]) for row in rows) + 1
        for row in rows:
            lines.append(f"  {row['label'] + ':':<{width + 1}} {row['value']}")

    lines.extend(["", "Nachricht:", message.message])

    attachments = list(message.attachments.all())
    if attachments:
        lines.extend(["", f"Anhänge ({len(attachments)}):"])
        for attachment in attachments:
            lines.append(f"  - {attachment.original_name} ({attachment.size_display})")
        if sum(item.size for item in attachments) > MAX_MAIL_ATTACHMENT_BYTES:
            lines.append("  (zu groß für den Mailversand - bitte im CMS ansehen)")

    lines.extend([
        "",
        "------------------------------------------",
        "Diese Anfrage liegt auch im CMS unter Benachrichtigungen.",
    ])
    return "\n".join(lines)


def _attach_files(mail, message):
    """Anhaenge der Anfrage an die Mail haengen, solange sie zusammen passen.

    Fehler beim Lesen einer Datei duerfen die Mail nicht verhindern: die Anfrage
    selbst ist wichtiger als ihr Anhang, und im CMS liegt beides ohnehin.
    """
    attachments = list(message.attachments.all())
    if not attachments:
        return

    if sum(item.size for item in attachments) > MAX_MAIL_ATTACHMENT_BYTES:
        logger.info(
            "Kontaktanfrage #%s: Anhänge zu groß für den Mailversand, nur im CMS abrufbar.",
            message.pk,
        )
        return

    for attachment in attachments:
        try:
            with attachment.file.open("rb") as handle:
                mail.attach(
                    attachment.original_name or f"anhang-{attachment.pk}",
                    handle.read(),
                    attachment.content_type or "application/octet-stream",
                )
        except Exception:
            logger.exception(
                "Anhang #%s der Kontaktanfrage #%s konnte nicht angehängt werden.",
                attachment.pk,
                message.pk,
            )


def build_confirmation_body(message: Message) -> str:
    meta = contact_category_meta(message.category)
    company = _company_name()
    lines = [
        f"Guten Tag {message.name},",
        "",
        f"vielen Dank für Ihre Anfrage ({meta['label']}). Wir haben sie erhalten und",
        "melden uns in der Regel innerhalb von zwei Werktagen bei Ihnen.",
        "",
        "Ihre Angaben zur Übersicht:",
    ]
    if message.title:
        lines.append(f"  Betreff: {message.title}")
    for row in message.detail_rows:
        lines.append(f"  {row['label']}: {row['value']}")
    lines.extend([
        "",
        message.message,
        "",
        "Bitte antworten Sie nicht auf diese automatische Bestätigung.",
        "",
        "Mit freundlichen Grüßen",
        company,
    ])
    return "\n".join(lines)


def send_contact_message(message: Message, send_confirmation: bool = True) -> bool:
    """Anfrage an die Genossenschaft schicken (und den Absender bestaetigen).

    Gibt zurueck, ob die interne Benachrichtigung rausging. Fehler werden
    protokolliert, aber nicht weitergereicht - die Anfrage selbst ist gespeichert.
    """
    meta = contact_category_meta(message.category)
    recipient = _recipient()
    sender = _sender()

    if not recipient:
        logger.error("Kontaktanfrage #%s: keine Empfängeradresse konfiguriert.", message.pk)
        return False

    subject = f"[{meta['short']}] {message.title or 'Neue Anfrage'} - {message.name}"
    internal = EmailMessage(
        subject=subject,
        body=build_internal_body(message),
        from_email=sender,
        to=[recipient],
        # Antworten im Postfach gehen direkt an den Absender der Anfrage.
        reply_to=[message.email],
    )

    # Nur die interne Mail bekommt die Anhaenge. Die Bestaetigung an den Absender
    # braucht sie nicht - er hat die Dateien selbst geschickt.
    _attach_files(internal, message)

    sent = False
    try:
        sent = bool(internal.send(fail_silently=False))
    except Exception:
        logger.exception("Kontaktanfrage #%s konnte nicht an %s gesendet werden.", message.pk, recipient)
        return False

    if send_confirmation:
        confirmation = EmailMessage(
            subject=f"Ihre Anfrage bei {_company_name()}",
            body=build_confirmation_body(message),
            from_email=sender,
            to=[message.email],
            reply_to=[recipient],
        )
        try:
            confirmation.send(fail_silently=False)
        except Exception:
            logger.exception("Bestätigung zu Kontaktanfrage #%s konnte nicht gesendet werden.", message.pk)

    return sent
