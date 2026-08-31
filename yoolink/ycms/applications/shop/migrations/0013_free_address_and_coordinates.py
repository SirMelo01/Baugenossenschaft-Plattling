import uuid

from django.db import migrations, models
from django.utils.text import slugify


def _free_slug(Brand, name):
    """Eindeutigen Slug bilden - das historische Modell kann das nicht selbst."""
    base = slugify(name)[:240] or str(uuid.uuid4())[:8]
    slug = base
    counter = 2
    while Brand.objects.filter(slug=slug).exists():
        suffix = f"-{counter}"
        slug = f"{base[:255 - len(suffix)]}{suffix}"
        counter += 1
    return slug


def location_becomes_address(apps, schema_editor):
    """Den Standort zurueck in das freie Adressfeld holen.

    Migration 0012 hatte den umgekehrten Weg genommen: getippte Anschriften wurden
    zu Standort-Eintraegen, weil beide Felder nebeneinander auf der Immobilienseite
    standen. Die Anschrift wird jetzt wieder direkt an der Immobilie eingegeben -
    dieselbe Anschrift darf dabei an mehreren Objekten stehen, ohne dass dafuer ein
    gemeinsamer Eintrag gepflegt werden muss.

    Die Zuordnung wird geloest, damit im CMS nicht ein unsichtbarer Standort neben
    der bearbeiteten Adresse stehen bleibt und beide auseinanderlaufen. Die
    Standort-Eintraege selbst bleiben erhalten, falls jemand sie noch braucht.
    """
    Product = apps.get_model("shop", "Product")

    for product in Product.objects.filter(brand__isnull=False).select_related("brand").iterator():
        address = (product.address or "").strip() or (product.brand.name or "").strip()
        Product.objects.filter(pk=product.pk).update(address=address[:255], brand=None)


def address_becomes_location(apps, schema_editor):
    """Beim Zurueckrollen wieder einen Standort je Anschrift anlegen (wie in 0012)."""
    Product = apps.get_model("shop", "Product")
    Brand = apps.get_model("shop", "Brand")

    for product in Product.objects.filter(brand__isnull=True).exclude(address="").iterator():
        name = (product.address or "").strip()[:255]
        if not name:
            continue
        brand = Brand.objects.filter(name=name).first()
        if brand is None:
            brand = Brand.objects.create(name=name, website="", slug=_free_slug(Brand, name))
        Product.objects.filter(pk=product.pk).update(brand=brand)


class Migration(migrations.Migration):

    dependencies = [
        ("shop", "0012_address_from_location"),
    ]

    operations = [
        migrations.AlterField(
            model_name="product",
            name="address",
            field=models.CharField(
                blank=True,
                default="",
                help_text='Frei eingetippte Anschrift, z.B. "Schillerstr. 6b, 94447 Plattling". Mehrere Immobilien duerfen dieselbe Anschrift tragen.',
                max_length=255,
                verbose_name="Adresse",
            ),
        ),
        migrations.AddField(
            model_name="product",
            name="latitude",
            field=models.FloatField(blank=True, editable=False, null=True, verbose_name="Breitengrad"),
        ),
        migrations.AddField(
            model_name="product",
            name="longitude",
            field=models.FloatField(blank=True, editable=False, null=True, verbose_name="Laengengrad"),
        ),
        migrations.RunPython(location_becomes_address, address_becomes_location),
    ]
