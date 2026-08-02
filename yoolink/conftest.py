import pytest

from yoolink.users.models import User
from yoolink.users.tests.factories import UserFactory


@pytest.fixture(autouse=True)
def media_storage(settings, tmpdir):
    settings.MEDIA_ROOT = tmpdir.strpath
    settings.STORAGES["default"] = {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    }


@pytest.fixture
def user(db) -> User:
    return UserFactory()
