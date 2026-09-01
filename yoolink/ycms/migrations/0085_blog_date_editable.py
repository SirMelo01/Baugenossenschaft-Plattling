import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):
    """Das Blogdatum wird eingetippt statt automatisch gesetzt.

    Bewusst von Hand geschrieben: ``makemigrations`` wuerde hier zusaetzlich alle
    ``*_en``-Spalten der Uebersetzungsfelder loeschen. Die stehen nur deshalb im
    Migrationsstand, weil django-modeltranslation sie frueher aus
    ``settings.LANGUAGES`` erzeugt hat - mit dem Blogdatum hat das nichts zu tun.
    """

    dependencies = [
        ("ycms", "0084_faq_files"),
    ]

    operations = [
        migrations.AlterField(
            model_name="blog",
            name="date",
            field=models.DateField(default=django.utils.timezone.localdate, verbose_name="Datum"),
        ),
    ]
