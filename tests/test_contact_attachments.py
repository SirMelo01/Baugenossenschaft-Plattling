"""Sicherungsnetz für die Datei-Anhänge der Kontaktformulare.

Anhänge kommen von nicht angemeldeten Besuchern und enthalten personenbezogene
Daten (ausgefüllte Selbstauskunft, Fotos aus der Wohnung). Geprüft wird deshalb
beides: dass der gute Fall funktioniert, und dass die Wege zu, die ein
Angreifer nehmen würde, verschlossen sind.
"""

import io
import zlib

import pytest
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from test_contact_forms import MITGLIEDSCHAFT, REPARATUR

from yoolink.users.tests.factories import UserFactory
from yoolink.ycms.models import (
    ContactFormSettings,
    Message,
    MessageAttachment,
    WebsiteSettings,
)

pytestmark = pytest.mark.django_db


# --------------------------------------------------------------------------
# Hilfsmittel zum Bauen von Testdateien
# --------------------------------------------------------------------------

def make_image(name="foto.jpg", fmt="JPEG", size=(60, 40), content_type="image/jpeg", exif=None):
    from PIL import Image

    buffer = io.BytesIO()
    image = Image.new("RGB", size, (200, 30, 30))
    save_kwargs = {"exif": exif} if exif else {}
    image.save(buffer, format=fmt, **save_kwargs)
    return SimpleUploadedFile(name, buffer.getvalue(), content_type=content_type)


def make_pdf(name="selbstauskunft.pdf", body=b"Ausgefuellt und unterschrieben"):
    content = b"%PDF-1.7\n1 0 obj\n<<>>\nendobj\n" + body + b"\ntrailer\n<<>>\n%%EOF\n"
    return SimpleUploadedFile(name, content, content_type="application/pdf")


@pytest.fixture
def repair_settings():
    settings_obj = ContactFormSettings.for_form("reparatur")
    settings_obj.uploads_enabled = True
    settings_obj.allow_images = True
    settings_obj.allow_documents = False
    settings_obj.max_uploads = 5
    settings_obj.save()
    return settings_obj


@pytest.fixture
def membership_settings():
    settings_obj = ContactFormSettings.for_form("mitgliedschaft")
    settings_obj.uploads_enabled = True
    settings_obj.allow_images = True
    settings_obj.allow_documents = True
    settings_obj.max_uploads = 3
    settings_obj.save()
    return settings_obj


# --------------------------------------------------------------------------
# Der gute Fall
# --------------------------------------------------------------------------

def test_repair_request_stores_uploaded_photos(client, repair_settings):
    response = client.post(
        reverse("kontakt"),
        {**REPARATUR, "anhaenge": [make_image("schaden1.jpg"), make_image("schaden2.png", fmt="PNG")]},
    )

    assert response.status_code == 302
    attachments = list(Message.objects.get().attachments.all())
    assert len(attachments) == 2
    assert [a.kind for a in attachments] == ["image", "image"]
    assert [a.original_name for a in attachments] == ["schaden1.jpg", "schaden2.png"]
    assert all(a.size > 0 for a in attachments)


def test_membership_request_accepts_the_filled_pdf(client, membership_settings):
    response = client.post(reverse("kontakt"), {**MITGLIEDSCHAFT, "anhaenge": [make_pdf()]})

    assert response.status_code == 302
    attachment = Message.objects.get().attachments.get()
    assert attachment.kind == "document"
    assert attachment.content_type == "application/pdf"
    assert attachment.original_name == "selbstauskunft.pdf"


def test_upload_is_optional(client, repair_settings):
    """Die Selbstauskunft ist ausdrücklich freiwillig - ohne Datei muss es gehen."""
    response = client.post(reverse("kontakt"), REPARATUR)

    assert response.status_code == 302
    assert Message.objects.get().attachments.count() == 0


def test_attachments_are_sent_with_the_internal_mail(client, repair_settings):
    WebsiteSettings.objects.create(contact_email="buero@example.org")
    mail.outbox = []

    client.post(reverse("kontakt"), {**REPARATUR, "anhaenge": [make_image("schaden.jpg")]})

    internal, confirmation = mail.outbox
    assert [name for name, _content, _type in internal.attachments] == ["schaden.jpg"]
    assert "Anhänge (1)" in internal.body
    # Der Absender bekommt seine eigenen Dateien nicht zurückgeschickt.
    assert confirmation.attachments == []


# --------------------------------------------------------------------------
# Abwehr
# --------------------------------------------------------------------------

def test_uploads_are_refused_when_switched_off_in_the_cms(client):
    """Auch eine nachgebaute Anfrage darf nichts hochladen, wenn es aus ist."""
    settings_obj = ContactFormSettings.for_form("reparatur")
    settings_obj.uploads_enabled = False
    settings_obj.save()

    response = client.post(reverse("kontakt"), {**REPARATUR, "anhaenge": [make_image()]})

    assert response.status_code == 302
    assert Message.objects.get().attachments.count() == 0


def test_a_disguised_script_is_refused(client, repair_settings):
    """Eine PHP-Datei, die sich als Bild ausgibt, darf nicht durchkommen."""
    payload = SimpleUploadedFile("schaden.jpg", b"<?php system($_GET['c']); ?>", content_type="image/jpeg")

    response = client.post(reverse("kontakt"), {**REPARATUR, "anhaenge": [payload]})

    assert response.status_code == 200
    assert Message.objects.count() == 0
    assert MessageAttachment.objects.count() == 0


def test_a_pdf_is_refused_where_only_images_are_allowed(client, repair_settings):
    response = client.post(reverse("kontakt"), {**REPARATUR, "anhaenge": [make_pdf()]})

    assert response.status_code == 200
    assert Message.objects.count() == 0


def test_an_svg_is_refused(client, repair_settings):
    """SVG kann Skripte enthalten und steht deshalb nicht auf der Liste."""
    svg = b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'
    payload = SimpleUploadedFile("bild.svg", svg, content_type="image/svg+xml")

    response = client.post(reverse("kontakt"), {**REPARATUR, "anhaenge": [payload]})

    assert response.status_code == 200
    assert Message.objects.count() == 0


def test_more_files_than_allowed_are_refused(client, repair_settings):
    repair_settings.max_uploads = 2
    repair_settings.save()

    response = client.post(
        reverse("kontakt"),
        {**REPARATUR, "anhaenge": [make_image(f"f{i}.jpg") for i in range(3)]},
    )

    assert response.status_code == 200
    assert Message.objects.count() == 0


def test_an_oversized_file_is_refused(client, repair_settings, settings):
    from yoolink.ycms import contact_attachments

    settings.DATA_UPLOAD_MAX_MEMORY_SIZE = 50 * 1024 * 1024
    big = SimpleUploadedFile(
        "gross.jpg",
        b"\xff\xd8\xff" + b"0" * (contact_attachments.MAX_FILE_BYTES + 1),
        content_type="image/jpeg",
    )

    response = client.post(reverse("kontakt"), {**REPARATUR, "anhaenge": [big]})

    assert response.status_code == 200
    assert Message.objects.count() == 0


def test_a_decompression_bomb_is_refused(client, repair_settings):
    """Ein winziges PNG, das entpackt riesig wäre, darf Pillow nicht ausrollen."""
    width = height = 60000
    raw = zlib.compress(b"\x00" * ((width + 1) * 4), 9)
    header = (
        b"\x89PNG\r\n\x1a\n"
        + b"\x00\x00\x00\rIHDR"
        + width.to_bytes(4, "big")
        + height.to_bytes(4, "big")
        + b"\x08\x06\x00\x00\x00"
        + b"\x00\x00\x00\x00"
    )
    payload = SimpleUploadedFile("bombe.png", header + raw, content_type="image/png")

    response = client.post(reverse("kontakt"), {**REPARATUR, "anhaenge": [payload]})

    assert response.status_code == 200
    assert Message.objects.count() == 0


def test_the_visitors_filename_never_becomes_the_storage_name(client, repair_settings):
    """Ein Name mit Pfadanteilen darf nicht in die Ablage durchschlagen."""
    payload = make_image("../../../etc/passwd.jpg")

    client.post(reverse("kontakt"), {**REPARATUR, "anhaenge": [payload]})

    attachment = MessageAttachment.objects.get()
    assert ".." not in attachment.file.name
    assert attachment.file.name.startswith("anfragen/")
    assert "passwd" not in attachment.file.name
    # Als Anzeigename bleibt nur der Dateiname übrig, ohne Pfad.
    assert attachment.original_name == "passwd.jpg"


def test_image_metadata_is_stripped(client, repair_settings):
    """Fotos vom Handy tragen GPS-Daten - die dürfen nicht mitgespeichert werden."""
    from PIL import Image

    exif = Image.Exif()
    exif[0x010F] = "TestKamera"
    upload = make_image("mit-exif.jpg", exif=exif.tobytes())

    client.post(reverse("kontakt"), {**REPARATUR, "anhaenge": [upload]})

    attachment = MessageAttachment.objects.get()
    with attachment.file.open("rb") as handle:
        gespeichert = Image.open(handle)
        assert dict(gespeichert.getexif()) == {}


# --------------------------------------------------------------------------
# Ablage und Auslieferung
# --------------------------------------------------------------------------

def test_attachments_are_not_stored_in_the_public_media_folder(client, repair_settings, settings):
    """Der Standard-Storage legt alles öffentlich ab - Anhänge gehören woanders hin."""
    client.post(reverse("kontakt"), {**REPARATUR, "anhaenge": [make_image()]})

    attachment = MessageAttachment.objects.get()
    assert attachment.file.storage.location == settings.PRIVATE_MEDIA_ROOT
    assert settings.MEDIA_ROOT not in attachment.file.path
    # Ohne base_url gibt es gar keine öffentliche Adresse.
    with pytest.raises(ValueError):
        attachment.file.url


def test_attachment_download_requires_a_login(client, repair_settings):
    client.post(reverse("kontakt"), {**REPARATUR, "anhaenge": [make_image()]})
    attachment = MessageAttachment.objects.get()

    response = client.get(attachment.get_absolute_url())

    # Nicht angemeldet: kein Dateiinhalt, sondern Weiterleitung ins CMS, das
    # seinerseits zur Anmeldung schickt.
    assert response.status_code == 302
    assert not response.get("Content-Disposition")
    assert response["Location"].startswith("/cms")


def test_logged_in_staff_can_open_an_attachment(client, repair_settings):
    client.post(reverse("kontakt"), {**REPARATUR, "anhaenge": [make_image("schaden.jpg")]})
    attachment = MessageAttachment.objects.get()
    client.force_login(UserFactory(is_staff=True, is_superuser=True))

    response = client.get(attachment.get_absolute_url())

    assert response.status_code == 200
    assert response["Content-Type"] == "image/jpeg"
    assert response["X-Content-Type-Options"] == "nosniff"
    assert "no-store" in response["Cache-Control"]
    # Bilder dürfen eingebettet erscheinen, sie wurden beim Hochladen neu geschrieben.
    assert "inline" in response.get("Content-Disposition", "inline")


def test_a_pdf_is_only_delivered_as_a_download(client, membership_settings):
    client.post(reverse("kontakt"), {**MITGLIEDSCHAFT, "anhaenge": [make_pdf()]})
    attachment = MessageAttachment.objects.get()
    client.force_login(UserFactory(is_staff=True, is_superuser=True))

    response = client.get(attachment.get_absolute_url())

    assert response.status_code == 200
    assert "attachment" in response["Content-Disposition"]
    assert response["X-Content-Type-Options"] == "nosniff"


def test_deleting_a_request_removes_its_files(client, repair_settings):
    """Löschkonzept: mit der Anfrage müssen auch die Dateien verschwinden."""
    client.post(reverse("kontakt"), {**REPARATUR, "anhaenge": [make_image()]})
    attachment = MessageAttachment.objects.get()
    storage, name = attachment.file.storage, attachment.file.name
    assert storage.exists(name)

    Message.objects.all().delete()

    assert MessageAttachment.objects.count() == 0
    assert not storage.exists(name)


# --------------------------------------------------------------------------
# CMS
# --------------------------------------------------------------------------

def test_cms_notification_shows_the_attachments(client, repair_settings):
    client.post(reverse("kontakt"), {**REPARATUR, "anhaenge": [make_image("schaden.jpg")]})
    client.force_login(UserFactory(is_staff=True, is_superuser=True))

    notification = Message.objects.get().notifications.get()
    body = client.get(reverse("cms:notification-detail", args=[notification.pk])).content.decode()

    assert "Anhänge (1)" in body
    assert "schaden.jpg" in body
    assert MessageAttachment.objects.get().get_absolute_url() in body


def test_cms_page_saves_the_document_and_upload_settings(client):
    from yoolink.ycms.models import AnyFile

    vorlage = AnyFile.objects.create(file=make_pdf("vorlage.pdf"), title="Selbstauskunft")
    client.force_login(UserFactory(is_staff=True, is_superuser=True))

    response = client.post(
        reverse("cms:save_contact_form_settings"),
        {
            "mitgliedschaft_document": str(vorlage.pk),
            "mitgliedschaft_uploads_enabled": "on",
            "mitgliedschaft_allow_documents": "on",
            "mitgliedschaft_max_uploads": "4",
            "reparatur_uploads_enabled": "on",
            "reparatur_allow_images": "on",
            "reparatur_max_uploads": "99",
        },
    )

    assert response.status_code == 302
    mitgliedschaft = ContactFormSettings.for_form("mitgliedschaft")
    assert mitgliedschaft.document_id == vorlage.pk
    assert mitgliedschaft.uploads_enabled is True
    assert mitgliedschaft.allow_documents is True
    assert mitgliedschaft.allow_images is False
    assert mitgliedschaft.max_uploads == 4

    # Unsinnige Werte werden auf einen sinnvollen Bereich gestutzt.
    assert ContactFormSettings.for_form("reparatur").max_uploads == 10
    # Ohne Häkchen bleibt das allgemeine Formular aus.
    assert ContactFormSettings.for_form("allgemein").uploads_enabled is False


def test_contact_page_offers_the_configured_document_for_download(client):
    from yoolink.ycms.models import AnyFile

    vorlage = AnyFile.objects.create(file=make_pdf("vorlage.pdf"), title="Selbstauskunft")
    settings_obj = ContactFormSettings.for_form("mitgliedschaft")
    settings_obj.document = vorlage
    settings_obj.uploads_enabled = True
    settings_obj.save()

    body = client.get(reverse("kontakt")).content.decode()

    assert vorlage.file.url in body
    assert "Selbstauskunft herunterladen" in body
    assert 'enctype="multipart/form-data"' in body
    assert 'name="anhaenge"' in body


def test_form_without_uploads_has_no_file_field(client):
    settings_obj = ContactFormSettings.for_form("allgemein")
    settings_obj.uploads_enabled = False
    settings_obj.save()

    response = client.get(reverse("kontakt"))
    entry = {e["key"]: e for e in response.context["contact_forms"]}["allgemein"]

    assert "anhaenge" not in entry["form"].fields
