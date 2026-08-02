from django.db import migrations, models


def move_content_types(apps, schema_editor):
    ContentType = apps.get_model("contenttypes", "ContentType")
    for model_name in ("textcontent", "privacypolicy"):
        old_content_type = ContentType.objects.filter(
            app_label="ycms",
            model=model_name,
        ).first()
        if not old_content_type:
            continue

        target_exists = ContentType.objects.filter(
            app_label="cms_content",
            model=model_name,
        ).exists()
        if target_exists:
            continue

        old_content_type.app_label = "cms_content"
        old_content_type.save(update_fields=["app_label"])


def restore_content_types(apps, schema_editor):
    ContentType = apps.get_model("contenttypes", "ContentType")
    for model_name in ("textcontent", "privacypolicy"):
        current_content_type = ContentType.objects.filter(
            app_label="cms_content",
            model=model_name,
        ).first()
        if not current_content_type:
            continue

        target_exists = ContentType.objects.filter(
            app_label="ycms",
            model=model_name,
        ).exists()
        if target_exists:
            continue

        current_content_type.app_label = "ycms"
        current_content_type.save(update_fields=["app_label"])


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("contenttypes", "0002_remove_content_type_name"),
        ("ycms", "0066_move_page_content_to_content_app"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.CreateModel(
                    name="PrivacyPolicy",
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
                        ("use_html", models.BooleanField(default=False)),
                        ("content_text", models.TextField(blank=True, default="")),
                        ("content_html", models.TextField(blank=True, default="")),
                        ("updated_at", models.DateTimeField(auto_now=True)),
                    ],
                    options={
                        "db_table": "ycms_privacypolicy",
                    },
                ),
                migrations.CreateModel(
                    name="TextContent",
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
                        ("name", models.CharField(default="", max_length=50, unique=True)),
                        ("header", models.CharField(default="", max_length=100)),
                        ("header_de", models.CharField(default="", max_length=100, null=True)),
                        ("header_en", models.CharField(default="", max_length=100, null=True)),
                        ("title", models.CharField(default="", max_length=140)),
                        ("title_de", models.CharField(default="", max_length=140, null=True)),
                        ("title_en", models.CharField(default="", max_length=140, null=True)),
                        ("description", models.TextField(default="")),
                        ("description_de", models.TextField(default="", null=True)),
                        ("description_en", models.TextField(default="", null=True)),
                        ("buttonText", models.CharField(default="", max_length=120)),
                        ("buttonText_de", models.CharField(default="", max_length=120, null=True)),
                        ("buttonText_en", models.CharField(default="", max_length=120, null=True)),
                    ],
                    options={
                        "db_table": "ycms_textcontent",
                    },
                ),
            ],
        ),
        migrations.RunPython(move_content_types, reverse_code=restore_content_types),
    ]

