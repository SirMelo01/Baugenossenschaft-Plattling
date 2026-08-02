from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("shop", "0004_product_show_price_when_showcase_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="product",
            name="title",
            field=models.CharField(max_length=255),
        ),
        migrations.AddField(
            model_name="product",
            name="language",
            field=models.CharField(
                choices=[("de", "Deutsch"), ("en", "Englisch")],
                default="de",
                max_length=10,
            ),
        ),
        migrations.AddField(
            model_name="product",
            name="original",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="translations",
                to="shop.product",
            ),
        ),
    ]
