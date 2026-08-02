# Hand-written migration: ServiceLocation für die Standort-/Einzugsgebiet-Karte.

from decimal import Decimal

from django.db import migrations, models


SEED_LOCATIONS = [
    # (name, tagline, url, lat, lng, is_headquarters)
    ("Deggendorf", "Unser Hauptsitz in Niederbayern", "/webdesign-deggendorf/", "48.837200", "12.951600", True),
    ("Regensburg", "", "", "49.013400", "12.101600", False),
    ("Straubing", "", "", "48.877700", "12.573900", False),
    ("Landshut", "", "", "48.537100", "12.152100", False),
    ("Passau", "", "", "48.566500", "13.431200", False),
    ("Dingolfing", "", "", "48.629600", "12.492800", False),
    ("Vilshofen", "", "", "48.626200", "13.185700", False),
    ("Cham", "", "", "49.218600", "12.661800", False),
    ("Viechtach", "", "", "49.080100", "12.886600", False),
    ("Regen", "", "", "48.976300", "13.127600", False),
    ("Grafenau", "", "", "48.858100", "13.396700", False),
    ("Freyung", "", "", "48.809500", "13.547900", False),
]


def seed_locations(apps, schema_editor):
    ServiceLocation = apps.get_model("cms_content", "ServiceLocation")
    if ServiceLocation.objects.exists():
        return
    for index, (name, tagline, url, lat, lng, is_hq) in enumerate(SEED_LOCATIONS, start=1):
        ServiceLocation.objects.create(
            name=name,
            tagline=tagline,
            url=url,
            latitude=Decimal(lat),
            longitude=Decimal(lng),
            is_headquarters=is_hq,
            active=True,
            order=index,
        )


def unseed_locations(apps, schema_editor):
    ServiceLocation = apps.get_model("cms_content", "ServiceLocation")
    ServiceLocation.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ("cms_content", "0008_privacypolicy_content_html_de_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="ServiceLocation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(default="", max_length=120)),
                ("tagline", models.CharField(blank=True, default="", max_length=160)),
                ("url", models.CharField(blank=True, default="", max_length=300)),
                ("latitude", models.DecimalField(decimal_places=6, default=0, max_digits=9)),
                ("longitude", models.DecimalField(decimal_places=6, default=0, max_digits=9)),
                ("is_headquarters", models.BooleanField(default=False)),
                ("active", models.BooleanField(default=True)),
                ("order", models.PositiveIntegerField(db_index=True, default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "ycms_servicelocation",
                "ordering": ["order", "id"],
            },
        ),
        migrations.RunPython(seed_locations, unseed_locations),
    ]
