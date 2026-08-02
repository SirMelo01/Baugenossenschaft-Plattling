import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("ycms", "0075_pagelink_remove_button_css_classes_button_color_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="RecoveryBackup",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "trigger",
                    models.CharField(
                        choices=[("scheduled", "Automatisch"), ("manual", "Manuell")],
                        max_length=20,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("queued", "Wartet"),
                            ("running", "Läuft"),
                            ("succeeded", "Erfolgreich"),
                            ("failed", "Fehlgeschlagen"),
                        ],
                        default="queued",
                        max_length=20,
                    ),
                ),
                ("slot", models.PositiveSmallIntegerField(blank=True, null=True)),
                ("object_key", models.CharField(blank=True, default="", max_length=500)),
                ("filename", models.CharField(blank=True, default="", max_length=180)),
                ("size_bytes", models.PositiveBigIntegerField(default=0)),
                ("encrypted_sha256", models.CharField(blank=True, default="", max_length=64)),
                ("include_media", models.BooleanField(default=False)),
                ("storage_bucket", models.CharField(blank=True, default="", max_length=255)),
                ("storage_endpoint", models.CharField(blank=True, default="", max_length=255)),
                ("error_message", models.TextField(blank=True, default="")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("started_at", models.DateTimeField(blank=True, null=True)),
                ("finished_at", models.DateTimeField(blank=True, null=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="recovery_backups",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
    ]
