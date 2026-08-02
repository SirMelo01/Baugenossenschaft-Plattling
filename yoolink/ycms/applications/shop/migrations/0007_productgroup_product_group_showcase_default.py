import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("shop", "0006_shopsettings_product_sku_price_note_featured"),
    ]

    operations = [
        migrations.CreateModel(
            name="ProductGroup",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(max_length=255, unique=True)),
                ("slug", models.SlugField(blank=True, max_length=255, unique=True)),
                ("sort_order", models.PositiveIntegerField(default=0)),
            ],
            options={
                "verbose_name": "Produktgruppe",
                "verbose_name_plural": "Produktgruppen",
                "ordering": ["sort_order", "name"],
            },
        ),
        migrations.AddField(
            model_name="product",
            name="group",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="products",
                to="shop.productgroup",
            ),
        ),
        migrations.AlterField(
            model_name="product",
            name="showcase_only",
            field=models.BooleanField(default=True),
        ),
    ]
