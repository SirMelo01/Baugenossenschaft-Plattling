from django.db import migrations, models


def set_category_from_source(apps, schema_editor):
    """Bestehende Benachrichtigungen der passenden Art zuordnen.

    Vor dieser Aenderung liess sich die Art nur an der Verknuepfung ablesen:
    haengt eine Bestellung dran, war es eine Bestellung; haengt eine Anfrage
    dran, kam sie aus dem einen bisherigen Kontaktformular (also "allgemein").
    Alles andere bleibt ein allgemeiner Hinweis.
    """
    Notification = apps.get_model("notifications", "Notification")
    Notification.objects.filter(order__isnull=False).update(category="order")
    Notification.objects.filter(order__isnull=True, message__isnull=False).update(category="general")


class Migration(migrations.Migration):

    dependencies = [
        ("notifications", "0001_initial"),
        ("ycms", "0082_message_category_phone_details"),
    ]

    operations = [
        migrations.AddField(
            model_name="notification",
            name="category",
            field=models.CharField(
                choices=[
                    ("general", "Allgemeine Anfrage"),
                    ("membership", "Mitgliedschaft"),
                    ("repair", "Reparaturservice"),
                    ("order", "Bestellung"),
                    ("system", "Hinweis"),
                ],
                db_index=True,
                default="system",
                max_length=20,
            ),
        ),
        migrations.RunPython(set_category_from_source, migrations.RunPython.noop),
    ]
