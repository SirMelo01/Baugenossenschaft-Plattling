from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("cms_content", "0002_customer"),
    ]

    operations = [
        migrations.AlterField(
            model_name="customer",
            name="logo_style",
            field=models.CharField(
                choices=[
                    ("circle", "Logo rund (kompakt)"),
                    ("square", "Logo quadratisch (kompakt)"),
                    ("wide", "Logo breit (mit integriertem Text)"),
                    ("text", "Nur Text/Initialen (kein Logo)"),
                ],
                default="circle",
                max_length=10,
            ),
        ),
    ]
