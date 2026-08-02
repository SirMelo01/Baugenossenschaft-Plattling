from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("ycms", "0065_move_notification_to_notifications_app"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.DeleteModel(name="PrivacyPolicy"),
                migrations.DeleteModel(name="TextContent"),
            ],
        ),
    ]

