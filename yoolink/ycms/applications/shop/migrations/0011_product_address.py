from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("shop", "0010_product_price_optional"),
    ]

    operations = [
        migrations.AddField(
            model_name="product",
            name="address",
            field=models.CharField(
                blank=True,
                default="",
                max_length=255,
                verbose_name="Adresse",
            ),
        ),
    ]
