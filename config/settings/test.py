"""
With these settings, tests run faster.
"""

from .base import *  # noqa
from .base import env

# GENERAL
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#secret-key
SECRET_KEY = env(
    "DJANGO_SECRET_KEY",
    default="WiSN0BVpHldvHWyYgin2pW1YCiGT0eF8PSYOm6TM4QYstdTmUm5bFzEfS252NguB",
)
# https://docs.djangoproject.com/en/dev/ref/settings/#test-runner
TEST_RUNNER = "django.test.runner.DiscoverRunner"

# PASSWORDS
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#password-hashers
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

# EMAIL
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#email-backend
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

# DEBUGGING FOR TEMPLATES
# ------------------------------------------------------------------------------
TEMPLATES[0]["OPTIONS"]["debug"] = True  # type: ignore # noqa F405
# Your stuff...
# ------------------------------------------------------------------------------

# STORAGES
# ------------------------------------------------------------------------------
# Tests duerfen weder in den S3-Bucket schreiben noch echte Anhaenge liegen
# lassen. Beide Ablagen zeigen deshalb ins Dateisystem; das Verzeichnis fuer die
# privaten Anhaenge legt die Fixture in conftest.py je Testlauf neu an.
import tempfile  # noqa: E402

STORAGES["default"] = {"BACKEND": "django.core.files.storage.FileSystemStorage"}  # noqa F405
MEDIA_ROOT = tempfile.mkdtemp(prefix="bgp-test-media-")
PRIVATE_MEDIA_ROOT = tempfile.mkdtemp(prefix="bgp-test-private-")
STORAGES["private"] = {  # noqa F405
    "BACKEND": "config.settings.cdn.backends.PrivateFileSystemStorage",
    "OPTIONS": {"location": PRIVATE_MEDIA_ROOT},
}
