import hashlib
import io
import json
import zipfile
from datetime import datetime, timezone

from botocore.exceptions import ClientError
import pytest
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.urls import reverse

from yoolink.users.models import User
from yoolink.ycms.models import CMSRole, CMSUserRole, FAQ, RecoveryBackup, fileentry
from yoolink.ycms.permissions import ensure_system_roles, user_permissions
from yoolink.ycms.recovery import (
    RESTORE_CONFIRMATION_PHRASE,
    build_backup_archive,
    create_remote_backup,
    restore_backup_archive,
)


@pytest.mark.django_db
def test_owner_system_role_includes_recovery_permission():
    user = User.objects.create_user(username="owner-user", password="secret")
    role, _created = CMSRole.objects.update_or_create(
        slug="owner",
        defaults={
            "name": "OWNER",
            "permissions": ["dashboard.view"],
            "is_system": True,
        },
    )
    CMSUserRole.objects.create(user=user, role=role)

    assert "recovery.manage" in user_permissions(user)


@pytest.mark.django_db
def test_recovery_manager_system_role_exists():
    roles = ensure_system_roles()

    assert "recovery-manager" in roles
    assert "recovery.manage" in roles["recovery-manager"].permissions


@pytest.mark.django_db
def test_recovery_backup_archive_contains_database_manifest_and_media():
    user = User.objects.create_superuser(username="backup-admin", password="secret")
    fileentry.objects.create(
        title="Backup Test",
        file=ContentFile(b"image-bytes", name="backup-test.jpg"),
    )

    archive, filename = build_backup_archive(user=user, include_media=True)

    assert filename.startswith("yoolink-backup-")
    assert filename.endswith(".zip")

    with zipfile.ZipFile(archive) as backup_zip:
        names = set(backup_zip.namelist())
        assert "database/dump.json" in names
        assert "manifest.json" in names
        assert "README.txt" in names
        assert any(name.startswith("media/") for name in names)

        manifest = json.loads(backup_zip.read("manifest.json").decode("utf-8"))
        assert manifest["format"] == "yoolink-recovery-backup"
        assert manifest["created_by"]["username"] == "backup-admin"
        assert manifest["media"]["included_files"] >= 1

        dump = json.loads(backup_zip.read("database/dump.json").decode("utf-8"))
        assert any(obj["model"] == "ycms.fileentry" for obj in dump)

    archive.close()


@pytest.mark.django_db(transaction=True)
def test_recovery_restore_replaces_database_and_restores_media():
    user = User.objects.create_superuser(username="backup-admin", password="secret")
    entry = fileentry.objects.create(
        title="Before Backup",
        file=ContentFile(b"restore-image-bytes", name="restore-media-test.jpg"),
    )
    stored_name = entry.file.name
    archive, _filename = build_backup_archive(user=user, include_media=True)

    entry.delete()
    if default_storage.exists(stored_name):
        default_storage.delete(stored_name)
    FAQ.objects.create(question="After backup", answer="Should disappear")

    summary = restore_backup_archive(archive, restore_media=True)

    assert summary["restored_media_files"] >= 1
    assert fileentry.objects.filter(title="Before Backup").exists()
    assert not FAQ.objects.filter(question="After backup").exists()
    assert default_storage.exists(stored_name)


@pytest.mark.django_db
def test_recovery_backup_archive_can_skip_media_files():
    user = User.objects.create_superuser(username="backup-admin", password="secret")
    fileentry.objects.create(
        title="Backup Test",
        file=ContentFile(b"image-bytes", name="skip-media-test.jpg"),
    )

    archive, _filename = build_backup_archive(user=user, include_media=False)

    with zipfile.ZipFile(archive) as backup_zip:
        names = set(backup_zip.namelist())
        assert "database/dump.json" in names
        assert "manifest.json" in names
        assert not any("skip-media-test" in name for name in names)

        manifest = json.loads(backup_zip.read("manifest.json").decode("utf-8"))
        assert manifest["media"]["include_media"] is False
        assert manifest["media"]["included_files"] == 0
        assert manifest["media"]["skipped_files"] >= 1

    archive.close()


@pytest.mark.django_db
def test_recovery_restore_view_requires_confirmation_phrase(client):
    user = User.objects.create_superuser(username="backup-admin", password="secret")
    client.force_login(user)

    response = client.post(
        reverse("cms:recovery-backup-restore"),
        {"confirmation_phrase": "wrong"},
    )

    assert response.status_code == 400
    assert response.json()["success"] is False


@pytest.mark.django_db
def test_recovery_backup_download_view_returns_zip(client):
    user = User.objects.create_superuser(username="backup-admin", password="secret")
    client.force_login(user)

    response = client.get(reverse("cms:recovery-backup-download"))

    assert response.status_code == 200
    assert response["Cache-Control"].startswith("no-store")
    assert "attachment;" in response["Content-Disposition"]

    payload = b"".join(response.streaming_content)
    with zipfile.ZipFile(io.BytesIO(payload)) as backup_zip:
        assert "database/dump.json" in backup_zip.namelist()
        assert "manifest.json" in backup_zip.namelist()


@pytest.mark.django_db
def test_recovery_settings_view_renders_for_recovery_user(client):
    user = User.objects.create_user(username="recovery-user", password="secret")
    role = CMSRole.objects.create(
        name="Recovery",
        slug="recovery",
        permissions=["dashboard.view", "recovery.manage"],
    )
    CMSUserRole.objects.create(user=user, role=role)
    client.force_login(user)

    response = client.get(reverse("cms:recovery-settings"))

    assert response.status_code == 200
    assert b"Backup herunterladen" in response.content
    assert b"Backup wiederherstellen" in response.content
    assert b"Remote-Backup starten" in response.content


@pytest.mark.django_db
def test_recovery_remote_backup_start_requires_complete_configuration(client, settings):
    settings.RECOVERY_REMOTE_BACKUPS_ENABLED = False
    user = User.objects.create_superuser(username="backup-admin", password="secret")
    client.force_login(user)

    response = client.post(reverse("cms:recovery-remote-backup-start"))

    assert response.status_code == 400
    assert response.json()["success"] is False


@pytest.mark.django_db
def test_recovery_remote_backup_status_returns_recent_backups(client):
    user = User.objects.create_superuser(username="backup-admin", password="secret")
    backup_record = RecoveryBackup.objects.create(
        trigger=RecoveryBackup.TRIGGER_MANUAL,
        status=RecoveryBackup.STATUS_SUCCEEDED,
        slot=1,
        object_key="private/recovery-backups/slot-1.enc",
        filename="yoolink-backup.zip.enc",
        encrypted_sha256="a" * 64,
        created_by=user,
    )
    client.force_login(user)

    response = client.get(reverse("cms:recovery-remote-backup-status"))

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["backups"][0]["object_key"] == "private/recovery-backups/slot-1.enc"
    assert payload["backups"][0]["restore_url"] == reverse("cms:recovery-remote-backup-restore", args=[backup_record.id])


@pytest.mark.django_db
def test_recovery_remote_backup_restore_requires_confirmation_phrase(client):
    user = User.objects.create_superuser(username="backup-admin", password="secret")
    backup_record = RecoveryBackup.objects.create(
        trigger=RecoveryBackup.TRIGGER_MANUAL,
        status=RecoveryBackup.STATUS_SUCCEEDED,
        slot=1,
        object_key="private/recovery-backups/slot-1.enc",
        storage_bucket="private-yoolink-backups",
        created_by=user,
    )
    client.force_login(user)

    response = client.post(
        reverse("cms:recovery-remote-backup-restore", args=[backup_record.id]),
        {"confirmation_phrase": "wrong"},
    )

    assert response.status_code == 400
    assert response.json()["success"] is False


@pytest.mark.django_db(transaction=True)
def test_recovery_remote_backup_object_restore_accepts_valid_remote_backup(client, settings, monkeypatch):
    settings.RECOVERY_REMOTE_BACKUPS_ENABLED = True
    settings.RECOVERY_BACKUP_ENCRYPTION_KEY = "test-key"
    settings.RECOVERY_BACKUP_BUCKET_NAME = "private-yoolink-backups"
    settings.AWS_ACCESS_KEY_ID = "access-key"
    settings.AWS_SECRET_ACCESS_KEY = "secret-key"
    settings.AWS_S3_ENDPOINT_URL = "https://fra1.digitaloceanspaces.com/"

    user = User.objects.create_superuser(username="backup-admin", password="secret")
    fileentry.objects.create(title="Remote Restore", file=ContentFile(b"remote-restore", name="remote-restore.jpg"))
    archive, _filename = build_backup_archive(user=user, include_media=True)
    archive_payload = archive.read()
    archive_hash = hashlib.sha256(archive_payload).hexdigest()
    archive.close()

    class FakeStreamingBody:
        def __init__(self, payload):
            self.buffer = io.BytesIO(payload)

        def read(self, size=-1):
            return self.buffer.read(size)

        def close(self):
            self.buffer.close()

    class FakeS3Client:
        def get_object(self, **kwargs):
            assert kwargs["Bucket"] == "private-yoolink-backups"
            assert kwargs["Key"] == "private/recovery-backups/slot-1.enc"
            return {
                "Body": FakeStreamingBody(archive_payload),
                "Metadata": {"yoolink-backup-sha256": archive_hash},
            }

    monkeypatch.setattr("yoolink.ycms.recovery._remote_backup_client", lambda: FakeS3Client())

    FAQ.objects.create(question="After remote backup", answer="Should disappear")
    client.force_login(user)

    response = client.post(
        reverse("cms:recovery-remote-backup-object-restore"),
        {
            "confirmation_phrase": RESTORE_CONFIRMATION_PHRASE,
            "object_key": "private/recovery-backups/slot-1.enc",
            "restore_media": "on",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["summary"]["restored_media_files"] >= 1
    assert fileentry.objects.filter(title="Remote Restore").exists()
    assert not FAQ.objects.filter(question="After remote backup").exists()


@pytest.mark.django_db
def test_recovery_remote_backup_status_includes_storage_slots_without_db_record(client, settings, monkeypatch):
    settings.RECOVERY_REMOTE_BACKUPS_ENABLED = True
    settings.RECOVERY_BACKUP_ENCRYPTION_KEY = "test-key"
    settings.RECOVERY_BACKUP_BUCKET_NAME = "private-yoolink-backups"
    settings.RECOVERY_BACKUP_PREFIX = "private/recovery-backups"
    settings.RECOVERY_REMOTE_BACKUP_ROTATION_SLOTS = 2
    settings.AWS_ACCESS_KEY_ID = "access-key"
    settings.AWS_SECRET_ACCESS_KEY = "secret-key"
    settings.AWS_S3_ENDPOINT_URL = "https://fra1.digitaloceanspaces.com/"

    class FakeS3Client:
        def head_object(self, **kwargs):
            assert kwargs["Bucket"] == "private-yoolink-backups"
            if kwargs["Key"] == "private/recovery-backups/slot-1.enc":
                return {
                    "ContentLength": 1234,
                    "LastModified": datetime(2026, 6, 14, tzinfo=timezone.utc),
                    "Metadata": {
                        "yoolink-backup-sha256": "b" * 64,
                        "yoolink-backup-include-media": "false",
                    },
                }
            raise ClientError({"Error": {"Code": "404"}}, "HeadObject")

    monkeypatch.setattr("yoolink.ycms.recovery._remote_backup_client", lambda: FakeS3Client())

    user = User.objects.create_superuser(username="backup-admin", password="secret")
    client.force_login(user)

    response = client.get(reverse("cms:recovery-remote-backup-status"))

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["backups"][0]["source"] == "storage"
    assert payload["backups"][0]["restore_url"] == reverse("cms:recovery-remote-backup-object-restore")
    assert payload["backups"][0]["object_key"] == "private/recovery-backups/slot-1.enc"


@pytest.mark.django_db
def test_remote_backup_upload_uses_private_acl_and_rotates_slots(settings, monkeypatch):
    settings.RECOVERY_REMOTE_BACKUPS_ENABLED = True
    settings.RECOVERY_BACKUP_ENCRYPTION_KEY = "test-key"
    settings.RECOVERY_BACKUP_BUCKET_NAME = "private-yoolink-backups"
    settings.RECOVERY_BACKUP_PREFIX = "private/recovery-backups"
    settings.RECOVERY_REMOTE_BACKUP_ROTATION_SLOTS = 2
    settings.RECOVERY_REMOTE_BACKUP_INCLUDE_MEDIA = False
    settings.AWS_ACCESS_KEY_ID = "access-key"
    settings.AWS_SECRET_ACCESS_KEY = "secret-key"
    settings.AWS_S3_ENDPOINT_URL = "https://fra1.digitaloceanspaces.com/"

    class FakeS3Client:
        def __init__(self):
            self.calls = []

        def put_object(self, **kwargs):
            kwargs["Body"].read()
            self.calls.append(kwargs)

    fake_client = FakeS3Client()
    monkeypatch.setattr("yoolink.ycms.recovery._remote_backup_client", lambda: fake_client)
    monkeypatch.setattr("yoolink.ycms.recovery.encrypt_backup_file", lambda archive: archive)

    user = User.objects.create_superuser(username="backup-admin", password="secret")

    first = create_remote_backup(trigger="manual", user=user)
    second = create_remote_backup(trigger="manual", user=user)
    third = create_remote_backup(trigger="manual", user=user)

    assert [first["slot"], second["slot"], third["slot"]] == [1, 2, 1]
    assert fake_client.calls[0]["Bucket"] == "private-yoolink-backups"
    assert fake_client.calls[0]["Key"] == "private/recovery-backups/slot-1.enc"
    assert fake_client.calls[0]["ACL"] == "private"
    assert fake_client.calls[0]["CacheControl"] == "no-store"
    assert fake_client.calls[0]["Metadata"]["yoolink-backup-format"] == "aesgcm-v1"
    assert RecoveryBackup.objects.filter(status=RecoveryBackup.STATUS_SUCCEEDED).count() == 3


@pytest.mark.django_db
def test_recovery_backup_download_view_can_skip_media(client):
    user = User.objects.create_superuser(username="backup-admin", password="secret")
    fileentry.objects.create(
        title="Backup Test",
        file=ContentFile(b"image-bytes", name="route-skip-media-test.jpg"),
    )
    client.force_login(user)

    response = client.get(reverse("cms:recovery-backup-download"), {"include_media": "0"})

    assert response.status_code == 200
    payload = b"".join(response.streaming_content)
    with zipfile.ZipFile(io.BytesIO(payload)) as backup_zip:
        names = set(backup_zip.namelist())
        assert not any("route-skip-media-test" in name for name in names)
        manifest = json.loads(backup_zip.read("manifest.json").decode("utf-8"))
        assert manifest["media"]["include_media"] is False
        assert manifest["media"]["skipped_files"] >= 1


@pytest.mark.django_db(transaction=True)
def test_recovery_restore_view_accepts_valid_backup(client):
    user = User.objects.create_superuser(username="backup-admin", password="secret")
    fileentry.objects.create(
        title="Restore Route",
        file=ContentFile(b"route-restore-image", name="route-restore-media-test.jpg"),
    )
    archive, filename = build_backup_archive(user=user, include_media=True)
    archive.seek(0)
    client.force_login(user)

    response = client.post(
        reverse("cms:recovery-backup-restore"),
        {
            "confirmation_phrase": RESTORE_CONFIRMATION_PHRASE,
            "backup_file": ContentFile(archive.read(), name=filename),
            "restore_media": "on",
        },
    )

    assert response.status_code == 200
    assert response.json()["success"] is True
