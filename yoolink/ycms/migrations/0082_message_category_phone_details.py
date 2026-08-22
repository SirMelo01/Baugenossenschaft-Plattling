from django.db import migrations, models


class Migration(migrations.Migration):
    """Kontaktanfragen bekommen eine Art, eine Telefonnummer und Zusatzangaben.

    Bestehende Anfragen stammen alle aus dem einen bisherigen Formular und sind
    damit "allgemein" - genau der Standardwert des neuen Feldes.
    """

    dependencies = [
        ("ycms", "0081_seed_baugenossenschaft_plattling_opening_hours"),
    ]

    operations = [
        migrations.AddField(
            model_name="message",
            name="category",
            field=models.CharField(
                choices=[
                    ("general", "Allgemeine Anfrage"),
                    ("membership", "Mitgliedschaft"),
                    ("repair", "Reparaturservice"),
                ],
                db_index=True,
                default="general",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="message",
            name="phone",
            field=models.CharField(blank=True, default="", max_length=40),
        ),
        migrations.AddField(
            model_name="message",
            name="details",
            field=models.JSONField(blank=True, default=list),
        ),
    ]
