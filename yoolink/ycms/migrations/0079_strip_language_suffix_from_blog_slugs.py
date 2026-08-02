from django.db import migrations


def strip_language_suffix_from_slugs(apps, schema_editor):
    """Entfernt bei bestehenden Blog-Übersetzungen das Sprach-Suffix
    (z. B. "-en", "-fr", "-de") aus dem Slug.

    Hintergrund: Übersetzungen wurden früher mit einem Slug im Format
    "<titel>-<sprache>" angelegt. Die Sprache steckt aber bereits im URL-Pfad
    (z. B. /en/blog/...), daher ist das Suffix im Slug redundant.

    Diese Migration geht bewusst sehr vorsichtig und idempotent vor:
      * Es werden ausschließlich Übersetzungen angefasst (``original`` gesetzt).
        Original-Blogs hatten nie ein Sprach-Suffix und bleiben unberührt.
      * Umbenannt wird nur, wenn der Slug wirklich auf "-<sprache>" endet
        (passend zur eigenen ``language`` des Blogs, damit kein zufälliges
        Wortende wie "...-de" fälschlich abgeschnitten wird).
      * Umbenannt wird nur, wenn der Ziel-Slug noch frei ist. Gäbe es eine
        Kollision, bleibt der bestehende Slug unverändert – lieber ein
        "-en" behalten als eine URL zerschießen.

    Alte URLs bleiben aufrufbar: Der Blog-Detail-View leitet einen abweichenden
    Slug automatisch (301) auf den aktuellen Slug um, und die ``pk`` – der
    stabile Teil der URL – ändert sich nie. Bereits indizierte Seiten bleiben
    also erreichbar und werden sauber auf die neue, kürzere URL geführt.
    """
    Blog = apps.get_model("ycms", "Blog")

    # Hinweis: der historische Blog aus apps.get_model hat KEINE eigene save()-
    # Logik. blog.save() ist hier das Standard-Django-save und generiert den
    # Slug nicht neu – genau das wollen wir.
    for blog in Blog.objects.filter(original__isnull=False).iterator():
        slug = blog.slug or ""
        language = (blog.language or "").lower()
        if not slug or not language:
            continue

        suffix = f"-{language}"
        if not slug.endswith(suffix):
            continue

        new_slug = slug[: -len(suffix)]
        if not new_slug:
            continue

        # Kollision vermeiden: nur umbenennen, wenn der Ziel-Slug frei ist.
        if Blog.objects.filter(slug=new_slug).exclude(pk=blog.pk).exists():
            continue

        blog.slug = new_slug
        blog.save(update_fields=["slug"])


class Migration(migrations.Migration):

    dependencies = [
        ("ycms", "0078_seed_cmsinfo_buttons"),
    ]

    operations = [
        # Bewusst nicht umkehrbar: das Wiederherstellen des exakten alten
        # Suffix-Zustands ist nicht verlustfrei möglich. Ein Rollback der
        # Migration lässt die Slugs einfach unverändert (noop).
        migrations.RunPython(
            strip_language_suffix_from_slugs,
            migrations.RunPython.noop,
        ),
    ]
