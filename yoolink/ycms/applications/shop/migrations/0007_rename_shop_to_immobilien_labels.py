from django.db import migrations, models


def seed_immobilien_settings(apps, schema_editor):
    ShopSettings = apps.get_model("shop", "ShopSettings")
    settings_obj = ShopSettings.objects.order_by("id").first()
    if settings_obj is None:
        settings_obj = ShopSettings.objects.create()
    settings_obj.products_layout = "grouped"
    settings_obj.products_title = "Immobilien"
    settings_obj.products_intro = (
        "Freie und vorgemerkte Objekte der Baugenossenschaft Plattling "
        "auf einen Blick."
    )
    settings_obj.save(update_fields=["products_layout", "products_title", "products_intro"])


class Migration(migrations.Migration):

    dependencies = [
        ("shop", "0006_shopsettings_product_sku_price_note_featured"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="productgroup",
            options={"ordering": ["sort_order", "name"], "verbose_name": "Immobilienrubrik", "verbose_name_plural": "Immobilienrubriken"},
        ),
        migrations.AlterModelOptions(
            name="shopsettings",
            options={"verbose_name": "Immobilien Einstellungen", "verbose_name_plural": "Immobilien Einstellungen"},
        ),
        migrations.AlterField(
            model_name="product",
            name="price_note",
            field=models.CharField(blank=True, default="", help_text='Optionaler Zusatz zum Preis, z.B. "Kaltmiete" oder "auf Anfrage".', max_length=120, verbose_name="Preishinweis"),
        ),
        migrations.AlterField(
            model_name="product",
            name="sku",
            field=models.CharField(blank=True, default="", max_length=64, verbose_name="Objektnummer"),
        ),
        migrations.AlterField(
            model_name="shopsettings",
            name="products_layout",
            field=models.CharField(choices=[("filter", "Immobilien mit Filterleiste"), ("grouped", "Gruppiert nach Rubriken")], default="filter", max_length=20),
        ),
        migrations.AlterField(
            model_name="shopsettings",
            name="products_title",
            field=models.CharField(default="Immobilien", max_length=120),
        ),
        migrations.RunPython(seed_immobilien_settings, migrations.RunPython.noop),
    ]
