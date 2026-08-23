from django.db import migrations, models


def _text(obj, field):
    """Deutschen Text lesen - modeltranslation legt ihn in "<feld>_de" ab.

    Das Basisfeld bleibt leer, solange die Standardsprache im CMS auf Englisch
    steht (siehe DEFAULT_LANGUAGE in ycms/views.py), deshalb hat das Feld mit
    Sprachsuffix Vorrang.
    """
    if obj is None:
        return ""
    return (getattr(obj, f"{field}_de", "") or getattr(obj, field, "") or "").strip()


def move_tenant_documents_into_faq(apps, schema_editor):
    """Den bisherigen Mieterinfo-Kasten in einen echten FAQ-Eintrag ueberfuehren.

    Bis hierher hat die Startseite die PDF-Karten unter dem FAQ selbst
    zusammengesucht: alle Dateien mit ".pdf" im Namen, davon bis zu zwei mit
    "mieter", "hausordnung", "nebenkosten" oder "info" im Titel. Gepflegt werden
    konnte daran nichts - genau deshalb faellt der Kasten weg und die Unterlagen
    haengen jetzt an der Frage, zu der sie gehoeren.

    Damit die Dateien beim Deployment nicht kommentarlos von der Seite
    verschwinden, legt diese Migration einmalig einen FAQ-Eintrag an und haengt
    dieselben PDFs daran, die der alte Kasten gezeigt haette. Frage und Antwort
    kommen aus den CMS-Texten des Kastens, sonst aus deren Standardwerten. Der
    Eintrag ist danach ein FAQ wie jedes andere und laesst sich umbenennen,
    umsortieren oder loeschen.
    """
    FAQ = apps.get_model("ycms", "FAQ")
    AnyFile = apps.get_model("ycms", "AnyFile")
    TextContent = apps.get_model("cms_content", "TextContent")

    documents = list(AnyFile.objects.filter(file__iendswith=".pdf").order_by("-uploaded_at")[:50])
    if not documents:
        return

    keywords = ("mieter", "miet", "hausordnung", "nebenkosten", "betriebskosten", "info", "information")

    def score(file_obj):
        text = f"{file_obj.title} {file_obj.file.name}".lower()
        return 0 if any(keyword in text for keyword in keywords) else 1

    ranked = sorted(enumerate(documents), key=lambda item: (score(item[1]), item[0]))
    selected = [file_obj for _, file_obj in ranked[:2]]
    if not selected:
        return

    texts = TextContent.objects.filter(name="main_bgp_tenant_infos").first()
    question = _text(texts, "title") or "Dokumente für Mieter"
    answer = _text(texts, "description") or (
        "Die wichtigsten Unterlagen stehen hier direkt als PDF zum Herunterladen bereit."
    )

    max_order = FAQ.objects.aggregate(models.Max("order"))["order__max"]
    faq = FAQ.objects.create(
        question=question,
        question_de=question,
        answer=answer,
        answer_de=answer,
        order=1 if max_order is None else max_order + 1,
    )
    faq.files.set(selected)


def drop_migrated_faq(apps, schema_editor):
    """Beim Zurueckrollen faellt die Zuordnung mit der Spalte ohnehin weg."""


class Migration(migrations.Migration):

    dependencies = [
        ("cms_content", "0009_servicelocation"),
        ("ycms", "0083_contact_attachments"),
    ]

    operations = [
        migrations.AddField(
            model_name="faq",
            name="files",
            field=models.ManyToManyField(blank=True, related_name="faqs", to="ycms.anyfile"),
        ),
        migrations.RunPython(move_tenant_documents_into_faq, drop_migrated_faq),
    ]
