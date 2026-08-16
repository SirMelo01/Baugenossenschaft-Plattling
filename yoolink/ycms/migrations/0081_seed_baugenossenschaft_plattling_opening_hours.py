from datetime import time

from django.db import migrations

# Buerozeiten der Baugenossenschaft Plattling: Mo, Mi und Fr von 8 bis 12 Uhr.
# Die Kontaktseite und die Kachel auf der Startseite lesen diese Zeiten aus dem
# Modul "Oeffnungszeiten"; ohne Datensaetze blieben beide leer.
OPEN_DAYS = ("MON", "WED", "FRI")
ALL_DAYS = ("MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN")


def seed_opening_hours(apps, schema_editor):
    WebsiteSettings = apps.get_model("ycms", "WebsiteSettings")
    OpeningHours = apps.get_model("ycms", "OpeningHours")

    settings_obj = WebsiteSettings.objects.order_by("id").first()
    if settings_obj is None:
        return

    # Nur anlegen, was fehlt: gepflegte Zeiten duerfen nicht ueberschrieben werden.
    existing = set(
        OpeningHours.objects.filter(website=settings_obj).values_list("day", flat=True)
    )
    OpeningHours.objects.bulk_create(
        [
            OpeningHours(
                website=settings_obj,
                day=day,
                is_open=day in OPEN_DAYS,
                start_time=time(8, 0),
                end_time=time(12, 0),
                has_lunch_break=False,
            )
            for day in ALL_DAYS
            if day not in existing
        ]
    )


class Migration(migrations.Migration):
    dependencies = [
        ("ycms", "0080_seed_baugenossenschaft_plattling_settings"),
    ]

    operations = [
        migrations.RunPython(seed_opening_hours, migrations.RunPython.noop),
    ]
