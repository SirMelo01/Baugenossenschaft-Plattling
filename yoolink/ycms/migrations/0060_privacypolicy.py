from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("ycms", "0059_usersettings_two_factor_email_code_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="PrivacyPolicy",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("use_html", models.BooleanField(default=False)),
                ("content_text", models.TextField(blank=True, default="")),
                ("content_html", models.TextField(blank=True, default="")),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
        ),
    ]
