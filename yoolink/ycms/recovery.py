import hashlib
import io
import json
import os
import posixpath
import struct
import tempfile
import zipfile
from collections import OrderedDict
from datetime import datetime

import boto3
import django
from botocore.exceptions import BotoCoreError, ClientError
from django.apps import apps
from django.conf import settings
from django.core import serializers
from django.core.files.base import File
from django.core.files.storage import FileSystemStorage, storages
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import models
from django.db import transaction
from django.utils import timezone


BACKUP_FORMAT_VERSION = "1.0"
BACKUP_DB_PATH = "database/dump.json"
BACKUP_MANIFEST_PATH = "manifest.json"
BACKUP_README_PATH = "README.txt"
RESTORE_CONFIRMATION_PHRASE = "YooLink Recovery wiederherstellen"
ENCRYPTED_BACKUP_MAGIC = b"YOOLINK-RECOVERY-BACKUP-AESGCM-V1\n"


def _setting_value(name, default=""):
    value = getattr(settings, name, default)
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _safe_archive_name(name):
    normalized = posixpath.normpath(str(name).replace("\\", "/")).lstrip("/")
    if normalized in {"", "."} or normalized.startswith("../") or "/../" in normalized:
        digest = hashlib.sha256(str(name).encode("utf-8")).hexdigest()[:12]
        return f"unsafe-name-{digest}"
    return normalized


def _safe_zip_member_name(name):
    normalized = posixpath.normpath(str(name).replace("\\", "/")).lstrip("/")
    if normalized in {"", "."} or normalized.startswith("../") or "/../" in normalized:
        raise ValueError(f"Unsicherer ZIP-Pfad: {name}")
    return normalized


def _database_metadata():
    database = settings.DATABASES.get("default", {})
    return {
        "engine": database.get("ENGINE", ""),
        "name": database.get("NAME", ""),
        "host": database.get("HOST", ""),
        "port": database.get("PORT", ""),
        "user": database.get("USER", ""),
        "password": "[redacted]" if database.get("PASSWORD") else "",
        "dump_file": BACKUP_DB_PATH,
        "format": "django-serializers-json",
    }


def _storage_metadata():
    default_storage = storages["default"]
    storage_settings = settings.STORAGES.get("default", {})
    cdn_settings = OrderedDict()
    for name in (
        "AWS_STORAGE_BUCKET_NAME",
        "AWS_S3_ENDPOINT_URL",
        "AWS_LOCATION",
        "AWS_QUERYSTRING_AUTH",
        "MEDIA_URL",
    ):
        cdn_settings[name] = _setting_value(name)

    cdn_settings["AWS_ACCESS_KEY_ID"] = "[redacted]" if _setting_value("AWS_ACCESS_KEY_ID") else ""
    cdn_settings["AWS_SECRET_ACCESS_KEY"] = "[redacted]" if _setting_value("AWS_SECRET_ACCESS_KEY") else ""

    return {
        "default_backend": f"{default_storage.__class__.__module__}.{default_storage.__class__.__name__}",
        "configured_backend": storage_settings.get("BACKEND", ""),
        "include_media_by_default": media_included_by_default(),
        "media_root": str(_setting_value("MEDIA_ROOT")),
        "public_media_url": _setting_value("MEDIA_URL"),
        "cdn": cdn_settings,
    }


def media_included_by_default():
    return isinstance(storages["default"], FileSystemStorage)


def _remote_backup_setting(name, default=""):
    return getattr(settings, name, default)


def remote_backups_enabled():
    return bool(_remote_backup_setting("RECOVERY_REMOTE_BACKUPS_ENABLED", False))


def remote_backups_configured():
    return all([
        remote_backups_enabled(),
        _remote_backup_setting("RECOVERY_BACKUP_ENCRYPTION_KEY", ""),
        _remote_backup_setting("RECOVERY_BACKUP_BUCKET_NAME", ""),
        _remote_backup_setting("AWS_ACCESS_KEY_ID", ""),
        _remote_backup_setting("AWS_SECRET_ACCESS_KEY", ""),
        _remote_backup_setting("AWS_S3_ENDPOINT_URL", ""),
    ])


def get_remote_backup_config_status():
    missing = []
    if not remote_backups_enabled():
        missing.append("RECOVERY_REMOTE_BACKUPS_ENABLED")
    for setting_name in (
        "RECOVERY_BACKUP_ENCRYPTION_KEY",
        "RECOVERY_BACKUP_BUCKET_NAME",
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_S3_ENDPOINT_URL",
    ):
        if not _remote_backup_setting(setting_name, ""):
            missing.append(setting_name)

    return {
        "enabled": remote_backups_enabled(),
        "configured": not missing,
        "missing": missing,
        "bucket": _remote_backup_setting("RECOVERY_BACKUP_BUCKET_NAME", ""),
        "endpoint": _remote_backup_setting("AWS_S3_ENDPOINT_URL", ""),
        "prefix": str(_remote_backup_setting("RECOVERY_BACKUP_PREFIX", "private/recovery-backups")).strip("/"),
        "slots": max(2, int(_remote_backup_setting("RECOVERY_REMOTE_BACKUP_ROTATION_SLOTS", 2) or 2)),
        "include_media": bool(_remote_backup_setting("RECOVERY_REMOTE_BACKUP_INCLUDE_MEDIA", False)),
    }


def _load_encryption_key():
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    except ImportError as exc:
        raise ValueError("cryptography ist nicht installiert; verschlüsselte Recovery-Backups sind nicht verfügbar.") from exc

    raw_key = _remote_backup_setting("RECOVERY_BACKUP_ENCRYPTION_KEY", "")
    if not raw_key:
        raise ValueError("RECOVERY_BACKUP_ENCRYPTION_KEY ist nicht konfiguriert.")

    import base64

    try:
        key = base64.urlsafe_b64decode(raw_key.encode("ascii"))
    except Exception as exc:
        raise ValueError("RECOVERY_BACKUP_ENCRYPTION_KEY ist kein gültiger base64-Key.") from exc

    if len(key) != 32:
        raise ValueError("RECOVERY_BACKUP_ENCRYPTION_KEY muss 32 Byte base64-kodiert enthalten.")
    return AESGCM(key)


def encrypt_backup_file(source_file):
    source_file.seek(0)
    encrypted_file = tempfile.TemporaryFile(mode="w+b")
    aesgcm = _load_encryption_key()
    encrypted_file.write(ENCRYPTED_BACKUP_MAGIC)

    while True:
        chunk = source_file.read(1024 * 1024)
        if not chunk:
            break
        nonce = os.urandom(12)
        encrypted_chunk = aesgcm.encrypt(nonce, chunk, ENCRYPTED_BACKUP_MAGIC)
        encrypted_file.write(struct.pack(">I", len(nonce)))
        encrypted_file.write(nonce)
        encrypted_file.write(struct.pack(">I", len(encrypted_chunk)))
        encrypted_file.write(encrypted_chunk)

    encrypted_file.seek(0)
    return encrypted_file


def decrypt_backup_file(source_file):
    source_file.seek(0)
    magic = source_file.read(len(ENCRYPTED_BACKUP_MAGIC))
    if magic != ENCRYPTED_BACKUP_MAGIC:
        source_file.seek(0)
        return source_file

    aesgcm = _load_encryption_key()
    decrypted_file = tempfile.TemporaryFile(mode="w+b")

    while True:
        nonce_length_bytes = source_file.read(4)
        if not nonce_length_bytes:
            break
        if len(nonce_length_bytes) != 4:
            raise ValueError("Verschlüsseltes Backup ist beschädigt.")
        nonce_length = struct.unpack(">I", nonce_length_bytes)[0]
        nonce = source_file.read(nonce_length)
        encrypted_length_bytes = source_file.read(4)
        if len(nonce) != nonce_length or len(encrypted_length_bytes) != 4:
            raise ValueError("Verschlüsseltes Backup ist beschädigt.")
        encrypted_length = struct.unpack(">I", encrypted_length_bytes)[0]
        encrypted_chunk = source_file.read(encrypted_length)
        if len(encrypted_chunk) != encrypted_length:
            raise ValueError("Verschlüsseltes Backup ist beschädigt.")
        decrypted_file.write(aesgcm.decrypt(nonce, encrypted_chunk, ENCRYPTED_BACKUP_MAGIC))

    decrypted_file.seek(0)
    if hasattr(source_file, "close"):
        source_file.close()
    return decrypted_file


def _runtime_settings_metadata():
    public_settings = OrderedDict()
    for name in (
        "DEBUG",
        "TIME_ZONE",
        "LANGUAGE_CODE",
        "SITE_ID",
        "ROOT_URLCONF",
        "DJANGO_SETTINGS_MODULE",
    ):
        public_settings[name] = _setting_value(name)

    return {
        "django_version": django.get_version(),
        "settings_module": _setting_value("DJANGO_SETTINGS_MODULE"),
        "settings": public_settings,
        "installed_apps": list(settings.INSTALLED_APPS),
    }


def iter_referenced_media_files():
    for model in apps.get_models():
        file_fields = [
            field for field in model._meta.fields
            if isinstance(field, models.FileField)
        ]
        if not file_fields:
            continue

        values = model._base_manager.all().values_list(
            model._meta.pk.name,
            *[field.name for field in file_fields],
        )
        for row in values.iterator(chunk_size=500):
            pk = row[0]
            for field, file_name in zip(file_fields, row[1:]):
                if not file_name:
                    continue
                yield {
                    "model": model._meta.label,
                    "pk": pk,
                    "field": field.name,
                    "name": str(file_name),
                    "storage_backend": f"{field.storage.__class__.__module__}.{field.storage.__class__.__name__}",
                    "storage": field.storage,
                }


def collect_media_references():
    files = OrderedDict()
    used_archive_paths = set()

    for reference in iter_referenced_media_files():
        name = reference["name"]
        if name not in files:
            archive_name = f"media/{_safe_archive_name(name)}"
            if archive_name in used_archive_paths:
                digest = hashlib.sha256(name.encode("utf-8")).hexdigest()[:12]
                archive_name = f"media/{digest}/{_safe_archive_name(name)}"
            used_archive_paths.add(archive_name)
            files[name] = {
                "name": name,
                "archive_path": archive_name,
                "storage_backend": reference["storage_backend"],
                "storage": reference["storage"],
                "references": [],
            }

        files[name]["references"].append({
            "model": reference["model"],
            "pk": reference["pk"],
            "field": reference["field"],
        })

    return files


def _iter_dump_objects():
    for model in apps.get_models():
        yield from model._base_manager.all().iterator(chunk_size=500)


def _write_database_dump(zip_file):
    with zip_file.open(BACKUP_DB_PATH, "w") as db_binary:
        db_text = io.TextIOWrapper(db_binary, encoding="utf-8", write_through=True)
        serializers.serialize(
            "json",
            _iter_dump_objects(),
            stream=db_text,
            indent=2,
            use_natural_foreign_keys=True,
            use_natural_primary_keys=True,
        )
        db_text.flush()
        db_text.detach()


def _copy_storage_file(zip_file, file_info):
    storage = file_info["storage"]
    name = file_info["name"]
    archive_path = file_info["archive_path"]
    hasher = hashlib.sha256()
    size = 0

    with storage.open(name, "rb") as source, zip_file.open(archive_path, "w") as target:
        while True:
            chunk = source.read(1024 * 1024)
            if not chunk:
                break
            target.write(chunk)
            hasher.update(chunk)
            size += len(chunk)

    return {
        "name": name,
        "archive_path": archive_path,
        "storage_backend": file_info["storage_backend"],
        "references": file_info["references"],
        "size": size,
        "sha256": hasher.hexdigest(),
        "status": "included",
    }


def _skipped_media_file(file_info):
    return {
        "name": file_info["name"],
        "archive_path": file_info["archive_path"],
        "storage_backend": file_info["storage_backend"],
        "references": file_info["references"],
        "status": "skipped-media-disabled",
    }


def _backup_readme(include_media):
    media_line = (
        "Dieses ZIP enthält auch die im CMS referenzierten Medien-Dateien.\n"
        if include_media
        else "Dieses ZIP enthält keine Medien-Dateien; sie wurden für diesen Export bewusst übersprungen.\n"
    )
    return (
        "YooLink CMS Recovery Backup\n"
        "===========================\n\n"
        "Dieses ZIP enthält einen Django JSON-Datenbankdump und ein Manifest.\n"
        f"{media_line}"
        "Die Datei manifest.json beschreibt Storage/CDN-Konfigurationen ohne geheime Zugangsdaten.\n\n"
        "Wichtig: Ein Restore überschreibt den aktuellen CMS-Datenbestand. "
        "Nutze dafür nur Backups aus einer vertrauenswürdigen Quelle.\n"
    )


def _copy_uploaded_file_to_temp(uploaded_file):
    temp_file = tempfile.TemporaryFile(mode="w+b")
    for chunk in uploaded_file.chunks():
        temp_file.write(chunk)
    temp_file.seek(0)
    return temp_file


def _open_backup_zip(uploaded_file_or_file):
    if hasattr(uploaded_file_or_file, "chunks"):
        temp_file = _copy_uploaded_file_to_temp(uploaded_file_or_file)
    else:
        temp_file = uploaded_file_or_file
        temp_file.seek(0)

    decrypted_file = None
    try:
        decrypted_file = decrypt_backup_file(temp_file)
        backup_zip = zipfile.ZipFile(decrypted_file)
    except zipfile.BadZipFile as exc:
        if hasattr(temp_file, "close"):
            temp_file.close()
        if decrypted_file is not None and decrypted_file is not temp_file and hasattr(decrypted_file, "close"):
            decrypted_file.close()
        raise ValueError("Die hochgeladene Datei ist kein gültiges ZIP-Backup.") from exc
    except ValueError:
        if hasattr(temp_file, "close"):
            temp_file.close()
        if decrypted_file is not None and decrypted_file is not temp_file and hasattr(decrypted_file, "close"):
            decrypted_file.close()
        raise

    for name in backup_zip.namelist():
        _safe_zip_member_name(name)
    return decrypted_file, backup_zip


def _load_backup_parts(backup_zip):
    names = set(backup_zip.namelist())
    missing_required = [name for name in (BACKUP_MANIFEST_PATH, BACKUP_DB_PATH) if name not in names]
    if missing_required:
        raise ValueError(f"Das Backup ist unvollständig: {', '.join(missing_required)} fehlt.")

    try:
        manifest = json.loads(backup_zip.read(BACKUP_MANIFEST_PATH).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("manifest.json ist nicht lesbar.") from exc

    if manifest.get("format") != "yoolink-recovery-backup":
        raise ValueError("Das ZIP ist kein YooLink Recovery Backup.")
    if manifest.get("format_version") != BACKUP_FORMAT_VERSION:
        raise ValueError("Die Backup-Version wird von dieser Installation nicht unterstützt.")

    db_dump = backup_zip.read(BACKUP_DB_PATH)
    try:
        json.loads(db_dump.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("database/dump.json ist kein gültiger JSON-Dump.") from exc

    return manifest, db_dump


def _validate_manifest_media_files(backup_zip, manifest):
    media = manifest.get("media") or {}
    files = media.get("files") or []
    names = set(backup_zip.namelist())
    for file_info in files:
        archive_path = _safe_zip_member_name(file_info.get("archive_path", ""))
        if archive_path not in names:
            raise ValueError(f"Medien-Datei fehlt im ZIP: {archive_path}")
        expected_hash = file_info.get("sha256")
        if expected_hash:
            hasher = hashlib.sha256()
            with backup_zip.open(archive_path, "r") as source:
                for chunk in iter(lambda: source.read(1024 * 1024), b""):
                    hasher.update(chunk)
            if hasher.hexdigest() != expected_hash:
                raise ValueError(f"Hash-Prüfung fehlgeschlagen: {archive_path}")


def inspect_backup_archive(uploaded_file_or_file):
    temp_file, backup_zip = _open_backup_zip(uploaded_file_or_file)
    try:
        manifest, _db_dump = _load_backup_parts(backup_zip)
        _validate_manifest_media_files(backup_zip, manifest)
        return build_restore_summary(manifest)
    finally:
        backup_zip.close()
        if hasattr(temp_file, "close"):
            temp_file.close()


def _restore_database_from_dump(db_dump):
    with tempfile.NamedTemporaryFile(mode="wb", suffix=".json") as dump_file:
        dump_file.write(db_dump)
        dump_file.flush()
        with transaction.atomic():
            call_command("flush", verbosity=0, interactive=False, reset_sequences=True)
            call_command("loaddata", dump_file.name, verbosity=0)


def _restore_media_files(backup_zip, manifest):
    restored = []
    storage = storages["default"]
    for file_info in (manifest.get("media") or {}).get("files") or []:
        name = file_info.get("name")
        archive_path = _safe_zip_member_name(file_info.get("archive_path", ""))
        if not name:
            continue
        if storage.exists(name):
            storage.delete(name)
        with backup_zip.open(archive_path, "r") as source:
            storage.save(name, File(source))
        restored.append(name)
    return restored


def restore_backup_archive(uploaded_file_or_file, *, restore_media=False):
    temp_file, backup_zip = _open_backup_zip(uploaded_file_or_file)
    try:
        manifest, db_dump = _load_backup_parts(backup_zip)
        _validate_manifest_media_files(backup_zip, manifest)
        _restore_database_from_dump(db_dump)
        restored_media = _restore_media_files(backup_zip, manifest) if restore_media else []
        summary = build_restore_summary(manifest)
        summary["restored_media_files"] = len(restored_media)
        summary["restore_media_requested"] = restore_media
        return summary
    except CommandError as exc:
        raise ValueError(f"Datenbank-Restore fehlgeschlagen: {exc}") from exc
    finally:
        backup_zip.close()
        if hasattr(temp_file, "close"):
            temp_file.close()


def build_restore_summary(manifest):
    media = manifest.get("media") or {}
    database = manifest.get("database") or {}
    runtime = manifest.get("runtime") or {}
    return {
        "created_at": manifest.get("created_at", ""),
        "created_by": manifest.get("created_by") or {},
        "database_engine": database.get("engine", ""),
        "settings_module": runtime.get("settings_module", ""),
        "referenced_media_files": media.get("referenced_files", 0),
        "included_media_files": media.get("included_files", 0),
        "skipped_media_files": media.get("skipped_files", 0),
        "missing_media_files": media.get("missing_files", 0),
        "failed_media_files": media.get("failed_files", 0),
        "backup_includes_media": bool(media.get("include_media")),
    }


def build_backup_archive(user=None, include_media=None):
    if include_media is None:
        include_media = media_included_by_default()

    created_at = timezone.now()
    archive = tempfile.TemporaryFile(mode="w+b")
    media_files = collect_media_references()
    included_files = []
    skipped_files = []
    missing_files = []
    failed_files = []

    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as zip_file:
        _write_database_dump(zip_file)

        if not include_media:
            skipped_files = [_skipped_media_file(file_info) for file_info in media_files.values()]

        media_to_copy = media_files.values() if include_media else []
        for file_info in media_to_copy:
            storage = file_info["storage"]
            name = file_info["name"]
            try:
                exists = storage.exists(name)
            except Exception as exc:
                failed_files.append({
                    "name": name,
                    "archive_path": file_info["archive_path"],
                    "references": file_info["references"],
                    "status": "exists-check-failed",
                    "error": str(exc),
                })
                continue

            if not exists:
                missing_files.append({
                    "name": name,
                    "archive_path": file_info["archive_path"],
                    "references": file_info["references"],
                    "status": "missing",
                })
                continue

            try:
                included_files.append(_copy_storage_file(zip_file, file_info))
            except Exception as exc:
                failed_files.append({
                    "name": name,
                    "archive_path": file_info["archive_path"],
                    "references": file_info["references"],
                    "status": "copy-failed",
                    "error": str(exc),
                })

        manifest = build_backup_manifest(
            created_at=created_at,
            user=user,
            included_files=included_files,
            skipped_files=skipped_files,
            missing_files=missing_files,
            failed_files=failed_files,
            include_media=include_media,
        )
        zip_file.writestr(BACKUP_MANIFEST_PATH, json.dumps(manifest, indent=2, ensure_ascii=False))
        zip_file.writestr(BACKUP_README_PATH, _backup_readme(include_media))

    archive.seek(0)
    filename = f"yoolink-backup-{created_at.strftime('%Y%m%d-%H%M%S')}.zip"
    return archive, filename


def build_backup_manifest(created_at, user, included_files, skipped_files, missing_files, failed_files, include_media):
    return {
        "format": "yoolink-recovery-backup",
        "format_version": BACKUP_FORMAT_VERSION,
        "created_at": created_at.isoformat(),
        "created_by": {
            "id": getattr(user, "id", None),
            "username": getattr(user, "username", ""),
            "is_superuser": bool(getattr(user, "is_superuser", False)),
        },
        "database": _database_metadata(),
        "runtime": _runtime_settings_metadata(),
        "storage": _storage_metadata(),
        "media": {
            "include_media": include_media,
            "include_media_by_default": media_included_by_default(),
            "referenced_files": len(included_files) + len(skipped_files) + len(missing_files) + len(failed_files),
            "included_files": len(included_files),
            "skipped_files": len(skipped_files),
            "missing_files": len(missing_files),
            "failed_files": len(failed_files),
            "files": included_files,
            "skipped": skipped_files,
            "missing": missing_files,
            "failed": failed_files,
        },
        "restore": {
            "import_ui_ready": True,
            "note": "Dieses Backup kann über Einstellungen > Recovery wiederhergestellt werden. Der Restore prüft Manifest, Datenbankdump und Medien-Hashes vor dem Import.",
        },
    }


def _remote_backup_client():
    return boto3.client(
        "s3",
        endpoint_url=_remote_backup_setting("AWS_S3_ENDPOINT_URL", ""),
        aws_access_key_id=_remote_backup_setting("AWS_ACCESS_KEY_ID", ""),
        aws_secret_access_key=_remote_backup_setting("AWS_SECRET_ACCESS_KEY", ""),
    )


def _next_remote_backup_slot():
    from yoolink.ycms.models import RecoveryBackup

    slots = max(2, int(_remote_backup_setting("RECOVERY_REMOTE_BACKUP_ROTATION_SLOTS", 2) or 2))
    latest = (
        RecoveryBackup.objects
        .filter(status=RecoveryBackup.STATUS_SUCCEEDED, slot__isnull=False)
        .order_by("-finished_at", "-created_at")
        .first()
    )
    if latest and latest.slot:
        return 1 if latest.slot >= slots else latest.slot + 1
    return 1


def _remote_backup_object_key(slot):
    prefix = str(_remote_backup_setting("RECOVERY_BACKUP_PREFIX", "private/recovery-backups")).strip("/")
    return f"{prefix}/slot-{slot}.enc"


def validate_remote_backup_object_key(object_key):
    clean_key = _safe_zip_member_name(object_key)
    prefix = str(_remote_backup_setting("RECOVERY_BACKUP_PREFIX", "private/recovery-backups")).strip("/")
    if prefix and not clean_key.startswith(f"{prefix}/"):
        raise ValueError("Remote-Backup liegt nicht im konfigurierten Backup-Prefix.")
    slots = max(2, int(_remote_backup_setting("RECOVERY_REMOTE_BACKUP_ROTATION_SLOTS", 2) or 2))
    valid_keys = {_remote_backup_object_key(slot) for slot in range(1, slots + 1)}
    if clean_key not in valid_keys:
        raise ValueError("Remote-Backup hat keinen gültigen Slot-Dateinamen.")
    return clean_key


def _file_hash_and_size(file_obj):
    file_obj.seek(0)
    hasher = hashlib.sha256()
    size = 0
    for chunk in iter(lambda: file_obj.read(1024 * 1024), b""):
        hasher.update(chunk)
        size += len(chunk)
    file_obj.seek(0)
    return hasher.hexdigest(), size


def create_remote_backup(*, trigger="manual", user=None, record_id=None):
    from yoolink.ycms.models import RecoveryBackup

    config_status = get_remote_backup_config_status()
    if record_id:
        record = RecoveryBackup.objects.get(id=record_id)
        record.trigger = trigger
        record.created_by = user if getattr(user, "is_authenticated", False) else record.created_by
        record.include_media = config_status["include_media"]
        record.storage_bucket = config_status["bucket"]
        record.storage_endpoint = config_status["endpoint"]
        record.save(update_fields=["trigger", "created_by", "include_media", "storage_bucket", "storage_endpoint"])
    else:
        record = RecoveryBackup.objects.create(
            trigger=trigger,
            status=RecoveryBackup.STATUS_QUEUED,
            created_by=user if getattr(user, "is_authenticated", False) else None,
            include_media=config_status["include_media"],
            storage_bucket=config_status["bucket"],
            storage_endpoint=config_status["endpoint"],
        )

    archive = None
    encrypted_archive = None
    try:
        if not config_status["configured"]:
            missing = ", ".join(config_status["missing"])
            raise ValueError(f"Remote-Backups sind nicht vollständig konfiguriert: {missing}")

        record.status = RecoveryBackup.STATUS_RUNNING
        record.started_at = timezone.now()
        record.slot = _next_remote_backup_slot()
        record.object_key = _remote_backup_object_key(record.slot)
        record.save(update_fields=["status", "started_at", "slot", "object_key"])

        archive, backup_filename = build_backup_archive(user=user, include_media=config_status["include_media"])
        encrypted_archive = encrypt_backup_file(archive)
        encrypted_sha256, encrypted_size = _file_hash_and_size(encrypted_archive)

        upload_filename = f"{backup_filename}.enc"
        client = _remote_backup_client()
        client.put_object(
            Bucket=config_status["bucket"],
            Key=record.object_key,
            Body=encrypted_archive,
            ACL="private",
            ContentType="application/octet-stream",
            CacheControl="no-store",
            Metadata={
                "yoolink-backup-format": "aesgcm-v1",
                "yoolink-backup-source": backup_filename,
                "yoolink-backup-trigger": trigger,
                "yoolink-backup-sha256": encrypted_sha256,
                "yoolink-backup-include-media": "true" if config_status["include_media"] else "false",
            },
        )

        record.status = RecoveryBackup.STATUS_SUCCEEDED
        record.filename = upload_filename
        record.size_bytes = encrypted_size
        record.encrypted_sha256 = encrypted_sha256
        record.finished_at = timezone.now()
        record.error_message = ""
        record.save(update_fields=[
            "status",
            "filename",
            "size_bytes",
            "encrypted_sha256",
            "finished_at",
            "error_message",
        ])
        return {
            "success": True,
            "backup_id": record.id,
            "slot": record.slot,
            "object_key": record.object_key,
            "size_bytes": record.size_bytes,
            "encrypted_sha256": record.encrypted_sha256,
        }
    except (BotoCoreError, ClientError, ValueError) as exc:
        record.status = RecoveryBackup.STATUS_FAILED
        record.error_message = str(exc)
        record.finished_at = timezone.now()
        record.save(update_fields=["status", "error_message", "finished_at"])
        raise
    finally:
        if archive is not None:
            archive.close()
        if encrypted_archive is not None:
            encrypted_archive.close()


def _copy_remote_body_to_temp(body):
    temp_file = tempfile.TemporaryFile(mode="w+b")
    try:
        while True:
            chunk = body.read(1024 * 1024)
            if not chunk:
                break
            temp_file.write(chunk)
        temp_file.seek(0)
        return temp_file
    except Exception:
        temp_file.close()
        raise
    finally:
        close = getattr(body, "close", None)
        if callable(close):
            close()


def download_remote_backup_object(object_key, *, bucket="", expected_hash=""):
    clean_key = validate_remote_backup_object_key(object_key)
    bucket = bucket or _remote_backup_setting("RECOVERY_BACKUP_BUCKET_NAME", "")
    if not bucket:
        raise ValueError("RECOVERY_BACKUP_BUCKET_NAME ist nicht konfiguriert.")

    try:
        response = _remote_backup_client().get_object(Bucket=bucket, Key=clean_key)
        backup_file = _copy_remote_body_to_temp(response["Body"])
    except (KeyError, BotoCoreError, ClientError) as exc:
        raise ValueError(f"Remote-Backup konnte nicht aus dem Storage geladen werden: {exc}") from exc

    metadata_hash = (response.get("Metadata") or {}).get("yoolink-backup-sha256", "")
    expected_hash = expected_hash or metadata_hash
    if expected_hash:
        actual_hash, _size = _file_hash_and_size(backup_file)
        if actual_hash != expected_hash:
            backup_file.close()
            raise ValueError("Hash-Prüfung des Remote-Backups fehlgeschlagen.")

    backup_file.seek(0)
    return backup_file


def download_remote_backup_file(record):
    if not record.object_key:
        raise ValueError("Dieses Remote-Backup hat keinen Storage-Pfad.")
    if record.status != record.STATUS_SUCCEEDED:
        raise ValueError("Nur erfolgreiche Remote-Backups können wiederhergestellt werden.")

    return download_remote_backup_object(
        record.object_key,
        bucket=record.storage_bucket,
        expected_hash=record.encrypted_sha256,
    )


def restore_remote_backup(record, *, restore_media=False):
    backup_file = download_remote_backup_file(record)
    return restore_backup_archive(backup_file, restore_media=restore_media)


def restore_remote_backup_object(object_key, *, restore_media=False):
    backup_file = download_remote_backup_object(object_key)
    return restore_backup_archive(backup_file, restore_media=restore_media)


def get_remote_backup_storage_slots():
    config_status = get_remote_backup_config_status()
    if not config_status["configured"]:
        return []

    client = _remote_backup_client()
    slots = []
    for slot in range(1, config_status["slots"] + 1):
        object_key = _remote_backup_object_key(slot)
        try:
            response = client.head_object(Bucket=config_status["bucket"], Key=object_key)
        except ClientError as exc:
            code = str((exc.response.get("Error") or {}).get("Code", ""))
            if code in {"404", "NoSuchKey", "NotFound"}:
                continue
            continue
        except BotoCoreError:
            continue

        metadata = response.get("Metadata") or {}
        include_media = metadata.get("yoolink-backup-include-media")
        slots.append({
            "id": None,
            "trigger": "Storage",
            "status": "succeeded",
            "status_label": "Im Storage",
            "slot": slot,
            "filename": posixpath.basename(object_key),
            "size_bytes": response.get("ContentLength", 0),
            "object_key": object_key,
            "encrypted_sha256": metadata.get("yoolink-backup-sha256", ""),
            "include_media": include_media == "true" if include_media in {"true", "false"} else None,
            "created_by": "",
            "created_at": response.get("LastModified").isoformat() if response.get("LastModified") else "",
            "started_at": "",
            "finished_at": response.get("LastModified").isoformat() if response.get("LastModified") else "",
            "error_message": "",
            "source": "storage",
        })
    return slots


def get_remote_backup_records(limit=6):
    from yoolink.ycms.models import RecoveryBackup

    return list(RecoveryBackup.objects.select_related("created_by").order_by("-created_at")[:limit])


def get_recovery_overview():
    models_with_data = 0
    total_objects = 0
    for model in apps.get_models():
        count = model._base_manager.count()
        if count:
            models_with_data += 1
            total_objects += count

    media_files = collect_media_references()
    return {
        "models_with_data": models_with_data,
        "total_objects": total_objects,
        "referenced_media_files": len(media_files),
        "include_media_by_default": media_included_by_default(),
        "restore_confirmation_phrase": RESTORE_CONFIRMATION_PHRASE,
        "database": _database_metadata(),
        "storage": _storage_metadata(),
        "remote_backup": get_remote_backup_config_status(),
        "remote_backup_records": get_remote_backup_records(),
        "generated_at": datetime.now().astimezone(),
    }
