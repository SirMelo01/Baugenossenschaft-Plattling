from django.db import migrations


CMSINFO_BUTTONS = [
    {
        "place": "main_cmsinfo_hero_cta",
        "color": "navy",
        "url": "/kontakt/",
        "icon": "",
        "target": "_self",
        "de": "Jetzt anfragen",
        "en": "Get in touch",
    },
    {
        "place": "main_cmsinfo_demo_cta",
        "color": "outline",
        "url": "#playground",
        "icon": "bi bi-cursor",
        "target": "_self",
        "de": "Direkt ausprobieren",
        "en": "Try it live",
    },
    {
        "place": "main_cmsinfo_products_cta",
        "color": "link",
        "url": "/products/",
        "icon": "bi bi-arrow-right",
        "target": "_self",
        "de": "Live-Beispiel: der Produkt-Showcase von YooLink",
        "en": "Live example: YooLink's product showcase",
    },
    {
        "place": "main_cmsinfo_bottomcta",
        "color": "navy",
        "url": "/kontakt/",
        "icon": "",
        "target": "_self",
        "de": "Lass uns gemeinsam starten",
        "en": "Let's get started",
    },
]


def seed_buttons(apps, schema_editor):
    """Legt die vier cmsinfo-Buttons an, falls der Slot noch leer ist
    (idempotent: bestehende/angepasste Buttons werden nicht überschrieben)."""
    Button = apps.get_model("ycms", "Button")
    for entry in CMSINFO_BUTTONS:
        if Button.objects.filter(place=entry["place"]).exists():
            continue
        Button.objects.create(
            place=entry["place"],
            color=entry["color"],
            url=entry["url"],
            icon=entry["icon"],
            target=entry["target"],
            text=entry["de"],
            text_de=entry["de"],
            text_en=entry["en"],
            order=0,
        )


def unseed_buttons(apps, schema_editor):
    Button = apps.get_model("ycms", "Button")
    Button.objects.filter(place__in=[e["place"] for e in CMSINFO_BUTTONS]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("ycms", "0077_button_place_alter_button_color"),
    ]

    operations = [
        migrations.RunPython(seed_buttons, unseed_buttons),
    ]
