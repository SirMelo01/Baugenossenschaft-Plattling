import uuid

from django.db import migrations
from django.utils.text import slugify


def _free_slug(Brand, name):
    """Eindeutigen Slug bilden - das historische Modell kann das nicht selbst.

    ``Brand.save()`` erzeugt den Slug normalerweise, in einer Migration steht
    aber nur das nackte Modell zur Verfuegung. Ohne Slug liefe der zweite
    Standort in die Unique-Bedingung.
    """
    base = slugify(name)[:240] or str(uuid.uuid4())[:8]
    slug = base
    counter = 2
    while Brand.objects.filter(slug=slug).exists():
        suffix = f"-{counter}"
        slug = f"{base[:255 - len(suffix)]}{suffix}"
        counter += 1
    return slug


def address_becomes_location(apps, schema_editor):
    """Getippte Anschriften in den Standort ueberfuehren.

    Bis hierher gab es zwei Felder fuer dasselbe: das freie Feld "Adresse" und
    die Zuordnung "Standort". Auf der Immobilienseite standen sie beide - deshalb
    ist das freie Feld weg und der Standort traegt die Anschrift.

    Objekte, bei denen nur die Adresse gepflegt war, bekommen hier einen Standort
    mit genau diesem Namen. Sonst wuerde ihre Anschrift beim naechsten Speichern
    im CMS verschwinden, weil dort nichts mehr steht, woraus sie kommen koennte.
    """
    Product = apps.get_model("shop", "Product")
    Brand = apps.get_model("shop", "Brand")

    for product in Product.objects.filter(brand__isnull=True).exclude(address="").iterator():
        name = (product.address or "").strip()[:255]
        if not name:
            continue
        brand = Brand.objects.filter(name=name).first()
        if brand is None:
            brand = Brand.objects.create(name=name, website="", slug=_free_slug(Brand, name))
        product.brand = brand
        product.save(update_fields=["brand"])


def location_stays(apps, schema_editor):
    """Die Adresse steht weiterhin am Objekt - beim Zurueckrollen ist nichts zu tun."""


class Migration(migrations.Migration):

    dependencies = [
        ("shop", "0011_product_address"),
    ]

    operations = [
        migrations.RunPython(address_becomes_location, location_stays),
    ]
