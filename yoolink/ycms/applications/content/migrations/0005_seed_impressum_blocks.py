from django.db import migrations


DEFAULT_BLOCKS = [
    {
        "title": "Haftungshinweis",
        "content": (
            "Trotz sorgfältiger inhaltlicher Kontrolle übernehmen wir keine Haftung für die "
            "Inhalte externer Links. Für den Inhalt der verlinkten Seiten sind ausschließlich "
            "deren Betreiber verantwortlich."
        ),
        "order": 0,
    },
    {
        "title": "Copyright",
        "content": (
            "© [[COMPANY]]. Alle Rechte vorbehalten.\n\n"
            "Text, Bilder, Grafiken und Videos unterliegen dem Schutz des Urheberrechts. "
            "Der Inhalt dieser Website darf nicht zu kommerziellen Zwecken kopiert, verbreitet "
            "oder verändert werden."
        ),
        "order": 1,
    },
    {
        "title": "Steuerliche Angaben",
        "content": "Gemäß § 19 UStG wird keine Umsatzsteuer berechnet.",
        "order": 2,
    },
]


def seed(apps, schema_editor):
    ImpressumBlock = apps.get_model("cms_content", "ImpressumBlock")
    if ImpressumBlock.objects.exists():
        return
    for block in DEFAULT_BLOCKS:
        ImpressumBlock.objects.create(active=True, **block)

    # Inhaber-Name in den Unternehmensdaten vorbelegen (bisher im Template fest hinterlegt).
    WebsiteSettings = apps.get_model("ycms", "WebsiteSettings")
    settings_obj = WebsiteSettings.objects.order_by("id").first()
    if settings_obj and not (settings_obj.owner_name or "").strip():
        settings_obj.owner_name = "Sebastian Rauch"
        settings_obj.save(update_fields=["owner_name"])


def unseed(apps, schema_editor):
    ImpressumBlock = apps.get_model("cms_content", "ImpressumBlock")
    ImpressumBlock.objects.filter(
        title__in=[b["title"] for b in DEFAULT_BLOCKS]
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("cms_content", "0004_impressumblock"),
        ("ycms", "0070_websitesettings_owner_name"),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
