from django.db import migrations


def strip_language_suffix_from_slugs(apps, schema_editor):
    """Entfernt bei bestehenden Produkt-Übersetzungen das Sprach-Suffix
    (z. B. "-en") aus dem Slug.

    Hintergrund: Übersetzungen wurden früher mit einem Slug im Format
    "<titel>-<sprache>" angelegt. Die Sprache steckt aber bereits im URL-Pfad
    (z. B. /en/products/...), daher ist das Suffix im Slug redundant.

    Sehr vorsichtig und idempotent:
      * Nur Übersetzungen (``original`` gesetzt); Original-Produkte hatten nie
        ein Sprach-Suffix und bleiben unberührt.
      * Nur wenn der Slug wirklich auf "-<sprache>" endet (passend zur eigenen
        ``language`` des Produkts).
      * Nur wenn der Ziel-Slug frei ist; gäbe es eine Kollision, bleibt der
        bestehende Slug unverändert – lieber ein "-en" behalten als eine URL
        zerschießen.

    Alte URLs bleiben erreichbar: die Produkt-Detail-View leitet einen
    abweichenden Slug per 301 auf den aktuellen um, und die ``pk`` – der stabile
    Teil der URL – ändert sich nie.
    """
    Product = apps.get_model("shop", "Product")

    # Der historische Product hat KEINE eigene save()-Logik; product.save() ist
    # hier das Standard-Django-save und erzeugt den Slug nicht neu.
    for product in Product.objects.filter(original__isnull=False).iterator():
        slug = product.slug or ""
        language = (product.language or "").lower()
        if not slug or not language:
            continue

        suffix = f"-{language}"
        if not slug.endswith(suffix):
            continue

        new_slug = slug[: -len(suffix)]
        if not new_slug:
            continue

        if Product.objects.filter(slug=new_slug).exclude(pk=product.pk).exists():
            continue

        product.slug = new_slug
        product.save(update_fields=["slug"])


class Migration(migrations.Migration):

    dependencies = [
        ("shop", "0007_productgroup_product_group_showcase_default"),
    ]

    operations = [
        migrations.RunPython(
            strip_language_suffix_from_slugs,
            migrations.RunPython.noop,
        ),
    ]
