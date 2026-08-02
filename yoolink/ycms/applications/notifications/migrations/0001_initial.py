import django.db.models.deletion
from django.db import migrations, models


def move_notification_content_type(apps, schema_editor):
    ContentType = apps.get_model("contenttypes", "ContentType")
    old_content_type = ContentType.objects.filter(
        app_label="ycms",
        model="notification",
    ).first()

    if not old_content_type:
        return

    target_exists = ContentType.objects.filter(
        app_label="notifications",
        model="notification",
    ).exists()
    if target_exists:
        return

    old_content_type.app_label = "notifications"
    old_content_type.save(update_fields=["app_label"])


def restore_notification_content_type(apps, schema_editor):
    ContentType = apps.get_model("contenttypes", "ContentType")
    current_content_type = ContentType.objects.filter(
        app_label="notifications",
        model="notification",
    ).first()

    if not current_content_type:
        return

    target_exists = ContentType.objects.filter(
        app_label="ycms",
        model="notification",
    ).exists()
    if target_exists:
        return

    current_content_type.app_label = "ycms"
    current_content_type.save(update_fields=["app_label"])


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("contenttypes", "0002_remove_content_type_name"),
        ("shop", "0001_initial"),
        ("ycms", "0065_move_notification_to_notifications_app"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.CreateModel(
                    name="Notification",
                    fields=[
                        (
                            "id",
                            models.BigAutoField(
                                auto_created=True,
                                primary_key=True,
                                serialize=False,
                                verbose_name="ID",
                            ),
                        ),
                        ("title", models.CharField(max_length=200)),
                        ("description", models.TextField(blank=True, default="")),
                        (
                            "priority",
                            models.CharField(
                                choices=[
                                    ("low", "Niedrig"),
                                    ("normal", "Normal"),
                                    ("high", "Hoch"),
                                ],
                                default="normal",
                                max_length=10,
                            ),
                        ),
                        ("seen", models.BooleanField(default=False)),
                        ("created_at", models.DateTimeField(auto_now_add=True)),
                        ("is_spam", models.BooleanField(default=False)),
                        ("link_url", models.URLField(blank=True, default="")),
                        (
                            "message",
                            models.ForeignKey(
                                blank=True,
                                null=True,
                                on_delete=django.db.models.deletion.SET_NULL,
                                related_name="notifications",
                                to="ycms.message",
                            ),
                        ),
                        (
                            "order",
                            models.ForeignKey(
                                blank=True,
                                null=True,
                                on_delete=django.db.models.deletion.SET_NULL,
                                related_name="notifications",
                                to="shop.order",
                            ),
                        ),
                    ],
                    options={
                        "db_table": "ycms_notification",
                        "ordering": ["-created_at"],
                        "indexes": [
                            models.Index(fields=["seen"], name="ycms_notifi_seen_cd2d30_idx"),
                            models.Index(fields=["created_at"], name="ycms_notifi_created_99aec2_idx"),
                            models.Index(fields=["is_spam"], name="ycms_notifi_is_spam_198dcc_idx"),
                        ],
                    },
                ),
            ],
        ),
        migrations.RunPython(
            move_notification_content_type,
            reverse_code=restore_notification_content_type,
        ),
    ]
