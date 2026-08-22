"""Prüfung und Bereinigung der Anhänge aus den Kontaktformularen.

Anhänge kommen von nicht angemeldeten Besuchern - alles daran ist zunächst
unglaubwürdig: Dateiname, Endung und der vom Browser gemeldete Inhaltstyp lassen
sich frei setzen. Dieses Modul entscheidet deshalb ausschließlich anhand des
tatsächlichen Dateiinhalts, was eine Datei ist, und gibt nur weiter, was es
selbst als unbedenklich erkannt hat:

* **Bilder** werden mit Pillow geöffnet, geprüft und neu geschrieben. Was dabei
  herauskommt, ist ein von Pillow erzeugtes Bild - eingebettete Skripte, an das
  Bild angehängte Fremddaten (Polyglot-Dateien) und die EXIF-Daten samt
  GPS-Koordinaten des Aufnahmeorts überleben das nicht.
* **PDF** lässt sich nicht sinnvoll neu schreiben. Hier prüfen wir Kennung und
  Größe, legen die Datei privat ab und liefern sie nur als Download aus - nie
  eingebettet im Browser.

Der Dateiname des Besuchers wird nie zum Ablagenamen: gespeichert wird unter
einem zufälligen Namen mit der Endung, die sich aus dem Inhalt ergibt.
"""

import io
import os
import uuid
from dataclasses import dataclass

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile

MB = 1024 * 1024

KIND_IMAGE = "image"
KIND_DOCUMENT = "document"

#: Größte erlaubte Einzeldatei.
MAX_FILE_BYTES = 10 * MB
#: Größte erlaubte Summe je Anfrage.
MAX_TOTAL_BYTES = 25 * MB
#: Obergrenze für die Kantenlänge gespeicherter Bilder. Größere werden verkleinert;
#: für die Beurteilung eines Schadens reicht das bei Weitem.
MAX_IMAGE_EDGE = 2400
#: Schutz vor "Dekompressionsbomben": ein kleines Bild, das entpackt den
#: Arbeitsspeicher sprengt. Pillow bekommt hier eine harte Obergrenze.
MAX_IMAGE_PIXELS = 40_000_000

#: Kennungen am Dateianfang -> (Endung, Inhaltstyp, Art). Nur was hier steht,
#: wird überhaupt angenommen.
_SIGNATURES = (
    (b"\x89PNG\r\n\x1a\n", ".png", "image/png", KIND_IMAGE),
    (b"\xff\xd8\xff", ".jpg", "image/jpeg", KIND_IMAGE),
    (b"%PDF-", ".pdf", "application/pdf", KIND_DOCUMENT),
)

#: Pillow-Format -> (Endung, Inhaltstyp). Bestimmt, wie ein Bild neu geschrieben wird.
_IMAGE_OUTPUT = {
    "JPEG": (".jpg", "image/jpeg"),
    "PNG": (".png", "image/png"),
    "WEBP": (".webp", "image/webp"),
}

ERLAUBTE_FORMATE = "JPG, PNG, WEBP und PDF"


@dataclass(frozen=True)
class PreparedAttachment:
    """Eine geprüfte, bereinigte Datei, bereit zum Speichern."""

    content: ContentFile
    storage_name: str
    original_name: str
    content_type: str
    kind: str
    size: int


def _read_header(upload, length=16):
    position = upload.tell() if hasattr(upload, "tell") else 0
    try:
        header = upload.read(length)
    finally:
        upload.seek(position if position is not None else 0)
    return header or b""


def _sniff(upload):
    """Art der Datei anhand des Inhalts. WEBP hat eine zweiteilige Kennung."""
    header = _read_header(upload)

    for signature, extension, content_type, kind in _SIGNATURES:
        if header.startswith(signature):
            return extension, content_type, kind

    if header.startswith(b"RIFF") and header[8:12] == b"WEBP":
        return ".webp", "image/webp", KIND_IMAGE

    return None, None, None


def _safe_display_name(upload, fallback):
    """Anzeigename für das CMS: nur der Dateiname, ohne Pfadanteile."""
    raw = os.path.basename((getattr(upload, "name", "") or "").replace("\\", "/")).strip()
    # Steuerzeichen entfernen; angezeigt wird der Name spaeter escaped.
    raw = "".join(char for char in raw if char.isprintable())
    return raw[:120] or fallback


def _rewrite_image(upload, label):
    """Bild öffnen, prüfen und als frisches Bild neu schreiben."""
    from PIL import Image, ImageFile

    previous_limit = Image.MAX_IMAGE_PIXELS
    Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS
    # Unvollstaendige Dateien sollen scheitern, nicht halb geladen werden.
    previous_truncated = ImageFile.LOAD_TRUNCATED_IMAGES
    ImageFile.LOAD_TRUNCATED_IMAGES = False

    try:
        upload.seek(0)
        try:
            probe = Image.open(upload)
            probe.verify()
        except Exception:
            raise ValidationError(f"{label}: Die Datei konnte nicht als Bild gelesen werden.")

        # ``verify()`` verbraucht das Bild - fuer das Neuschreiben neu oeffnen.
        upload.seek(0)
        try:
            image = Image.open(upload)
            image.load()
        except Exception:
            raise ValidationError(f"{label}: Die Datei konnte nicht als Bild gelesen werden.")

        image_format = (image.format or "").upper()
        if image_format not in _IMAGE_OUTPUT:
            image_format = "JPEG"
        extension, content_type = _IMAGE_OUTPUT[image_format]

        if max(image.size) > MAX_IMAGE_EDGE:
            image.thumbnail((MAX_IMAGE_EDGE, MAX_IMAGE_EDGE), Image.LANCZOS)

        save_kwargs = {}
        if image_format == "JPEG":
            # JPEG kann keine Transparenz; alles andere wuerde beim Speichern scheitern.
            if image.mode not in ("RGB", "L"):
                image = image.convert("RGB")
            save_kwargs = {"quality": 85, "optimize": True, "progressive": True}
        elif image_format == "PNG":
            save_kwargs = {"optimize": True}
        elif image_format == "WEBP":
            save_kwargs = {"quality": 85, "method": 4}

        buffer = io.BytesIO()
        # ``exif``/``icc_profile`` werden bewusst nicht uebernommen: das neue Bild
        # traegt keine Kamera-, Zeit- oder Ortsangaben mehr.
        image.save(buffer, format=image_format, **save_kwargs)
        buffer.seek(0)
        return buffer.getvalue(), extension, content_type
    finally:
        Image.MAX_IMAGE_PIXELS = previous_limit
        ImageFile.LOAD_TRUNCATED_IMAGES = previous_truncated


def _check_pdf(upload, label):
    """PDF: Kennung prüfen und unverändert übernehmen."""
    upload.seek(0)
    data = upload.read()
    upload.seek(0)

    if not data.startswith(b"%PDF-"):
        raise ValidationError(f"{label}: Die Datei ist kein gültiges PDF.")
    if b"%%EOF" not in data[-2048:]:
        raise ValidationError(f"{label}: Das PDF wirkt unvollständig. Bitte erneut exportieren und hochladen.")
    return data


def prepare_attachment(upload, allowed_kinds=(KIND_IMAGE, KIND_DOCUMENT), label="Datei"):
    """Eine hochgeladene Datei prüfen und bereinigt zurückgeben.

    Wirft ``ValidationError`` mit einem Text, der dem Besucher gezeigt werden kann.
    """
    size = int(getattr(upload, "size", 0) or 0)
    if size <= 0:
        raise ValidationError(f"{label}: Die Datei ist leer.")
    if size > MAX_FILE_BYTES:
        raise ValidationError(
            f"{label} ist zu groß ({size / MB:.1f} MB). Erlaubt sind bis zu {MAX_FILE_BYTES // MB} MB je Datei."
        )

    extension, content_type, kind = _sniff(upload)
    if kind is None or kind not in allowed_kinds:
        raise ValidationError(f"{label}: Dieses Dateiformat wird nicht angenommen. Erlaubt sind {ERLAUBTE_FORMATE}.")

    display_name = _safe_display_name(upload, fallback=f"anhang{extension}")

    if kind == KIND_IMAGE:
        data, extension, content_type = _rewrite_image(upload, label)
    else:
        data = _check_pdf(upload, label)

    if len(data) > MAX_FILE_BYTES:
        raise ValidationError(f"{label} ist auch nach der Verarbeitung zu groß.")

    return PreparedAttachment(
        content=ContentFile(data),
        # Der Name des Besuchers wird nie zum Ablagenamen.
        storage_name=f"{uuid.uuid4().hex}{extension}",
        original_name=display_name,
        content_type=content_type,
        kind=kind,
        size=len(data),
    )


def prepare_attachments(uploads, allowed_kinds=(KIND_IMAGE, KIND_DOCUMENT), max_files=5, label="Datei"):
    """Mehrere Dateien prüfen und dabei Anzahl und Gesamtgröße begrenzen."""
    uploads = [upload for upload in uploads if upload]
    if not uploads:
        return []

    if len(uploads) > max_files:
        raise ValidationError(f"Bitte hängen Sie höchstens {max_files} Dateien an (ausgewählt: {len(uploads)}).")

    prepared = []
    total = 0
    for index, upload in enumerate(uploads, start=1):
        einzel_label = label if len(uploads) == 1 else f"{label} {index}"
        item = prepare_attachment(upload, allowed_kinds=allowed_kinds, label=einzel_label)
        total += item.size
        if total > MAX_TOTAL_BYTES:
            raise ValidationError(
                f"Die Anhänge sind zusammen zu groß. Erlaubt sind insgesamt {MAX_TOTAL_BYTES // MB} MB."
            )
        prepared.append(item)

    return prepared
