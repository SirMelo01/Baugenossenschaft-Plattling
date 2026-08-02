from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("ycms", "0064_developerapiconnectauthorization"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.DeleteModel(
                    name="Notification",
                ),
            ],
        ),
    ]
