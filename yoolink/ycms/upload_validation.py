import os

from django.conf import settings
from django.core.exceptions import ValidationError


MB = 1024 * 1024

UPLOAD_KIND_IMAGE = "image"
UPLOAD_KIND_VIDEO = "video"
UPLOAD_KIND_DOCUMENT = "document"
UPLOAD_KIND_ARCHIVE = "archive"
UPLOAD_KIND_SUBTITLE = "subtitle"

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".webm"}
DOCUMENT_EXTENSIONS = {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".txt"}
ARCHIVE_EXTENSIONS = {".zip"}
SUBTITLE_EXTENSIONS = {".vtt"}
ANYFILE_EXTENSIONS = DOCUMENT_EXTENSIONS | ARCHIVE_EXTENSIONS

CONTENT_TYPE_EXTENSIONS = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "image/webp": ".webp",
    "video/mp4": ".mp4",
    "video/quicktime": ".mov",
    "video/webm": ".webm",
    "application/pdf": ".pdf",
    "application/zip": ".zip",
    "application/msword": ".doc",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "application/vnd.ms-excel": ".xls",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
    "application/vnd.ms-powerpoint": ".ppt",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": ".pptx",
    "text/plain": ".txt",
    "text/vtt": ".vtt",
}

DEFAULT_UPLOAD_LIMIT_BYTES = {
    UPLOAD_KIND_IMAGE: 12 * MB,
    UPLOAD_KIND_VIDEO: 250 * MB,
    UPLOAD_KIND_DOCUMENT: 50 * MB,
    UPLOAD_KIND_ARCHIVE: 100 * MB,
    UPLOAD_KIND_SUBTITLE: 1 * MB,
}


def configured_upload_limits():
    limits = dict(DEFAULT_UPLOAD_LIMIT_BYTES)
    limits.update(getattr(settings, "YCMS_UPLOAD_LIMIT_BYTES", {}) or {})
    return limits


def max_upload_size(upload_kind):
    return configured_upload_limits().get(upload_kind, DEFAULT_UPLOAD_LIMIT_BYTES[UPLOAD_KIND_DOCUMENT])


def format_file_size(size):
    size = int(size or 0)
    if size >= MB:
        mb_value = size / MB
        return f"{mb_value:.0f} MB" if mb_value.is_integer() else f"{mb_value:.1f} MB"
    kb_value = max(1, round(size / 1024))
    return f"{kb_value} KB"


def validation_error_message(error):
    if getattr(error, "messages", None):
        return str(error.messages[0])
    return str(error)


def _extension_from_signature(value):
    if not hasattr(value, "read"):
        return ""

    position = None
    try:
        if hasattr(value, "tell"):
            position = value.tell()
        header = value.read(16)
    except Exception:
        return ""
    finally:
        try:
            if position is not None:
                value.seek(position)
            else:
                value.seek(0)
        except Exception:
            pass

    if header.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if header.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if header.startswith((b"GIF87a", b"GIF89a")):
        return ".gif"
    if header.startswith(b"RIFF") and header[8:12] == b"WEBP":
        return ".webp"
    return ""


def file_extension(value):
    extension = os.path.splitext(getattr(value, "name", "") or "")[1].lower()
    if extension:
        return extension

    content_type = (getattr(value, "content_type", "") or "").split(";")[0].strip().lower()
    extension = CONTENT_TYPE_EXTENSIONS.get(content_type, "")
    if extension:
        return extension

    return _extension_from_signature(value)


def validate_extension(value, allowed_extensions, label="Datei"):
    extension = file_extension(value)
    if extension not in allowed_extensions:
        allowed = ", ".join(sorted(allowed_extensions))
        raise ValidationError(f"{label}: Dateiformat \"{extension or 'unbekannt'}\" wird nicht unterstuetzt. Erlaubt: {allowed}.")


def validate_upload_size(value, upload_kind, label="Datei"):
    size = int(getattr(value, "size", 0) or 0)
    max_size = max_upload_size(upload_kind)
    if size > max_size:
        raise ValidationError(
            f"{label} ist zu gross ({format_file_size(size)}). "
            f"Maximal erlaubt: {format_file_size(max_size)}."
        )


def validate_image_upload(value, label="Bild"):
    validate_extension(value, IMAGE_EXTENSIONS, label)
    validate_upload_size(value, UPLOAD_KIND_IMAGE, label)


def validate_video_upload(value, label="Video"):
    validate_extension(value, VIDEO_EXTENSIONS, label)
    validate_upload_size(value, UPLOAD_KIND_VIDEO, label)


def validate_video_thumbnail_upload(value, label="Thumbnail"):
    validate_extension(value, IMAGE_EXTENSIONS - {".gif"}, label)
    validate_upload_size(value, UPLOAD_KIND_IMAGE, label)


def validate_subtitle_upload(value, label="Untertiteldatei"):
    validate_extension(value, SUBTITLE_EXTENSIONS, label)
    validate_upload_size(value, UPLOAD_KIND_SUBTITLE, label)


def anyfile_upload_kind(value):
    extension = file_extension(value)
    if extension in IMAGE_EXTENSIONS:
        return UPLOAD_KIND_IMAGE
    if extension in VIDEO_EXTENSIONS:
        return UPLOAD_KIND_VIDEO
    if extension in ARCHIVE_EXTENSIONS:
        return UPLOAD_KIND_ARCHIVE
    return UPLOAD_KIND_DOCUMENT


def validate_anyfile_upload(value, label="Datei"):
    validate_extension(value, ANYFILE_EXTENSIONS, label)
    validate_upload_size(value, anyfile_upload_kind(value), label)
