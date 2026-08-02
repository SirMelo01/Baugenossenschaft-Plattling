from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("shop", "0005_product_language_original_and_title"),
    ]

    operations = [
        migrations.CreateModel(
            name="ShopSettings",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "products_layout",
                    models.CharField(
                        choices=[
                            ("filter", "Shop mit Filterleiste"),
                            ("grouped", "Gruppiert nach Kategorien"),
                        ],
                        default="filter",
                        max_length=20,
                    ),
                ),
                ("products_title", models.CharField(default="Produkte", max_length=120)),
                ("products_intro", models.TextField(blank=True)),
            ],
            options={
                "verbose_name": "Shop Einstellungen",
                "verbose_name_plural": "Shop Einstellungen",
            },
        ),
        migrations.AddField(
            model_name="product",
            name="sku",
            field=models.CharField(blank=True, default="", max_length=64, verbose_name="Artikelnummer"),
        ),
        migrations.AddField(
            model_name="product",
            name="price_note",
            field=models.CharField(
                blank=True,
                default="",
                help_text='Optionaler Zusatz zum Preis, z.B. "pro Stück" oder "zzgl. Versand".',
                max_length=120,
                verbose_name="Preishinweis",
            ),
        ),
        migrations.AddField(
            model_name="product",
            name="featured",
            field=models.BooleanField(default=False),
        ),
    ]
