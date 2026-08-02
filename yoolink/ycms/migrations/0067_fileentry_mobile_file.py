from django.db import migrations, models
import yoolink.ycms.models


class Migration(migrations.Migration):
    dependencies = [
        ("ycms", "0066_move_page_content_to_content_app"),
    ]

    operations = [
        migrations.AddField(
            model_name="fileentry",
            name="mobile_file",
            field=models.ImageField(
                blank=True,
                null=True,
                upload_to=yoolink.ycms.models.unique_image_name,
            ),
        ),
    ]
