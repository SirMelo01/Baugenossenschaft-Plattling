from django.db import migrations


def backfill_de(apps, schema_editor):
    """Bestehende (deutsche) Block-Inhalte in die de-Übersetzungsfelder kopieren."""
    ImpressumBlock = apps.get_model("cms_content", "ImpressumBlock")
    for block in ImpressumBlock.objects.all():
        update = {}
        if not (block.title_de or "").strip() and (block.title or "").strip():
            update["title_de"] = block.title
        if not (block.content_de or "").strip() and (block.content or "").strip():
            update["content_de"] = block.content
        if update:
            for field, value in update.items():
                setattr(block, field, value)
            block.save(update_fields=list(update.keys()))


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("cms_content", "0006_impressumblock_content_de_impressumblock_content_en_and_more"),
    ]

    operations = [
        migrations.RunPython(backfill_de, noop),
    ]
