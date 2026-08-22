import django.db.models.deletion
from django.db import migrations, models

import yoolink.ycms.models


def seed_contact_form_settings(apps, schema_editor):
    """Für jedes der drei Formulare einen Datensatz anlegen.

    Vorbelegt so, wie es fachlich passt: die Reparaturmeldung nimmt Fotos an, die
    Mitgliedsbewerbung die ausgefüllte Selbstauskunft. Welche PDF-Vorlage dort
    hängt, wählt die Genossenschaft selbst im CMS aus - das kann eine Migration
    nicht wissen.
    """
    ContactFormSettings = apps.get_model("ycms", "ContactFormSettings")
    defaults = {
        "allgemein": {"uploads_enabled": False, "max_uploads": 3, "allow_images": True, "allow_documents": True},
        "mitgliedschaft": {"uploads_enabled": True, "max_uploads": 3, "allow_images": True, "allow_documents": True},
        "reparatur": {"uploads_enabled": True, "max_uploads": 5, "allow_images": True, "allow_documents": False},
    }
    for form_key, values in defaults.items():
        ContactFormSettings.objects.update_or_create(form_key=form_key, defaults=values)


def drop_contact_form_settings(apps, schema_editor):
    apps.get_model("ycms", "ContactFormSettings").objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ("ycms", "0082_message_category_phone_details"),
    ]

    operations = [
        migrations.CreateModel(
            name="ContactFormSettings",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("form_key", models.CharField(max_length=20, unique=True)),
                ("uploads_enabled", models.BooleanField(default=False)),
                ("max_uploads", models.PositiveSmallIntegerField(default=3)),
                ("allow_images", models.BooleanField(default=True)),
                ("allow_documents", models.BooleanField(default=True)),
                (
                    "document",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="contact_forms",
                        to="ycms.anyfile",
                    ),
                ),
            ],
            options={
                "verbose_name": "Kontaktformular-Einstellung",
                "verbose_name_plural": "Kontaktformular-Einstellungen",
            },
        ),
        migrations.CreateModel(
            name="MessageAttachment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "file",
                    models.FileField(
                        max_length=255,
                        storage=yoolink.ycms.models.private_attachment_storage,
                        upload_to=yoolink.ycms.models.upload_to_message_attachment,
                    ),
                ),
                ("original_name", models.CharField(blank=True, default="", max_length=120)),
                ("content_type", models.CharField(blank=True, default="", max_length=100)),
                (
                    "kind",
                    models.CharField(
                        choices=[("image", "Bild"), ("document", "Dokument")],
                        default="document",
                        max_length=20,
                    ),
                ),
                ("size", models.PositiveIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "message",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="attachments",
                        to="ycms.message",
                    ),
                ),
            ],
            options={"ordering": ["id"]},
        ),
        migrations.RunPython(seed_contact_form_settings, drop_contact_form_settings),
    ]
