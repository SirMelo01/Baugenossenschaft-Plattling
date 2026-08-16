"""
Base settings to build other settings files upon.
"""
from pathlib import Path
import os
from django.utils.translation import gettext_lazy as _

import environ

BASE_DIR = Path(__file__).resolve(strict=True).parent.parent.parent
# yoolink/
APPS_DIR = BASE_DIR / "yoolink"
env = environ.Env()

READ_DOT_ENV_FILE = env.bool("DJANGO_READ_DOT_ENV_FILE", default=False)
if READ_DOT_ENV_FILE:
    # OS environment variables take precedence over variables from .env
    env.read_env(str(BASE_DIR / ".env"))

# GENERAL
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#debug
DEBUG = env.bool("DJANGO_DEBUG", False)

# Local time zone. Choices are
# http://en.wikipedia.org/wiki/List_of_tz_zones_by_name
# though not all of them may be available with every OS.
# In Windows, this must be set to your system time zone.
TIME_ZONE = "Europe/Berlin"
# https://docs.djangoproject.com/en/dev/ref/settings/#language-code
LANGUAGE_CODE = "de"
# https://docs.djangoproject.com/en/dev/ref/settings/#site-id
SITE_ID = 1
# Produktionsdomain dieser Seite. Einzige Stelle, an der die Domain gepflegt wird -
# ALLOWED_HOSTS, der www-Redirect, canonical-/OG-URLs, das JSON-LD und die Sitemap
# leiten sich davon ab. Per DJANGO_SITE_DOMAIN in der Env überschreibbar.
# Aktuell laeuft die Seite auf der Übergangs-Subdomain. Beim Umzug auf die
# Kundendomain hier auf "baugenossenschaft-plattling.de" umstellen und die
# Host-Regeln in compose/production/traefik/traefik.yml sowie nginx/default.conf
# mitziehen.
SITE_DOMAIN = env("DJANGO_SITE_DOMAIN", default="bgsplattling.yoolink.de")
SITE_BASE_URL = f"https://{SITE_DOMAIN}"
# https://docs.djangoproject.com/en/dev/ref/settings/#use-i18n
USE_I18N = True
# https://docs.djangoproject.com/en/dev/ref/settings/#use-tz
USE_TZ = True
# https://docs.djangoproject.com/en/dev/ref/settings/#locale-paths
LOCALE_PATHS = [str(BASE_DIR / "locale")]
# Languages
# Einzige Stelle, an der die aktiven Sprachen konfiguriert werden. Steht hier nur
# eine Sprache, blenden CMS und öffentliche Seite den Sprachumschalter komplett
# aus, es gibt keine /en-URLs mehr und ein englischer Browser bekommt trotzdem
# die deutsche Seite. Zum Reaktivieren einfach ('en', _('Englisch')) wieder
# eintragen - sonst ist nichts zu tun.
LANGUAGES = (
    ('de', _('Deutsch')),
)

# DATABASES
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#databases
DATABASES = {"default": env.db("DATABASE_URL")}
DATABASES["default"]["ATOMIC_REQUESTS"] = True
# https://docs.djangoproject.com/en/stable/ref/settings/#std:setting-DEFAULT_AUTO_FIELD
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# URLS
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#root-urlconf
ROOT_URLCONF = "config.urls"
# https://docs.djangoproject.com/en/dev/ref/settings/#wsgi-application
WSGI_APPLICATION = "config.wsgi.application"

# APPS
# ------------------------------------------------------------------------------
DJANGO_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.sites",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    "django.contrib.admin",
    "django.forms",
    "django.contrib.sitemaps",

]
THIRD_PARTY_APPS = [
    "crispy_forms",
    "crispy_bootstrap5",
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "django_celery_beat",
    "rest_framework",
    "rest_framework.authtoken",
    "corsheaders",
    "drf_spectacular",
    "django_recaptcha",
]

LOCAL_APPS = [
    "yoolink.users",
    # Your stuff: custom apps go here
    "yoolink.ycms",
    "yoolink.ycms.applications.content.apps.CmsContentConfig",
    "yoolink.ycms.applications.shop",
    "yoolink.ycms.applications.notifications.apps.NotificationsConfig",
    "yoolink.ycms.applications.blog.apps.CmsBlogApplicationConfig",
    "yoolink.blog",
]
# https://docs.djangoproject.com/en/dev/ref/settings/#installed-apps
INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

# MIGRATIONS
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#migration-modules
MIGRATION_MODULES = {"sites": "yoolink.contrib.sites.migrations"}

# AUTHENTICATION
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#authentication-backends
AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]
# https://docs.djangoproject.com/en/dev/ref/settings/#auth-user-model
AUTH_USER_MODEL = "users.User"
# https://docs.djangoproject.com/en/dev/ref/settings/#login-redirect-url
LOGIN_REDIRECT_URL = "users:redirect"
# https://docs.djangoproject.com/en/dev/ref/settings/#login-url
LOGIN_URL = "ycms:login"

# PASSWORDS
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#password-hashers
PASSWORD_HASHERS = [
    # https://docs.djangoproject.com/en/dev/topics/auth/passwords/#using-argon2-with-django
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
    "django.contrib.auth.hashers.BCryptSHA256PasswordHasher",
]
# https://docs.djangoproject.com/en/dev/ref/settings/#auth-password-validators
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"
    },
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# MIDDLEWARE
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#middleware
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "allauth.account.middleware.AccountMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "yoolink.middleware.WwwRedirectMiddleware",
]

# STATIC
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#static-root
STATIC_ROOT = str(BASE_DIR / "staticfiles")
# https://docs.djangoproject.com/en/dev/ref/settings/#static-url
STATIC_URL = "/static/"
# https://docs.djangoproject.com/en/dev/ref/contrib/staticfiles/#std:setting-STATICFILES_DIRS
STATICFILES_DIRS = [str(APPS_DIR / "static")]
# https://docs.djangoproject.com/en/dev/ref/contrib/staticfiles/#staticfiles-finders
STATICFILES_FINDERS = [
    "django.contrib.staticfiles.finders.FileSystemFinder",
    "django.contrib.staticfiles.finders.AppDirectoriesFinder",
]

# MEDIA
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#media-root
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')
# https://docs.djangoproject.com/en/dev/ref/settings/#media-url
MEDIA_URL = "/media/"

STORAGES = {
    "default": {
        "BACKEND": "config.settings.cdn.backends.MediaRootS3Boto3Storage",
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}

AWS_ACCESS_KEY_ID=env(
    "AWS_ACCESS_KEY_ID", 
    default="",
)
AWS_SECRET_ACCESS_KEY = env(
    "AWS_SECRET_ACCESS_KEY", 
    default="",
)
# Save Images in Cache and enable public access
AWS_S3_OBJECT_PARAMETERS = {
    "CacheControl": "max-age=300",
    "ACL": "public-read"
}
# No Auth URL, so just .../media/image.png
AWS_QUERYSTRING_AUTH = False
AWS_STORAGE_BUCKET_NAME='yoolink'
AWS_S3_ENDPOINT_URL='https://fra1.digitaloceanspaces.com/'
AWS_LOCATION = 'https://yoolink.fra1.digitaloceanspaces.com/'

# Recovery backups
# ------------------------------------------------------------------------------
# Remote recovery backups are encrypted before upload and written with private ACL.
# Keep RECOVERY_BACKUP_ENCRYPTION_KEY outside source control.
RECOVERY_REMOTE_BACKUPS_ENABLED = env.bool("RECOVERY_REMOTE_BACKUPS_ENABLED", default=False)
RECOVERY_BACKUP_ENCRYPTION_KEY = env("RECOVERY_BACKUP_ENCRYPTION_KEY", default="")
RECOVERY_BACKUP_BUCKET_NAME = env("RECOVERY_BACKUP_BUCKET_NAME", default=AWS_STORAGE_BUCKET_NAME)
RECOVERY_BACKUP_PREFIX = env("RECOVERY_BACKUP_PREFIX", default="private/bgp/recovery-backups")
RECOVERY_REMOTE_BACKUP_ROTATION_SLOTS = env.int("RECOVERY_REMOTE_BACKUP_ROTATION_SLOTS", default=2)
RECOVERY_REMOTE_BACKUP_INCLUDE_MEDIA = env.bool("RECOVERY_REMOTE_BACKUP_INCLUDE_MEDIA", default=False)

RECAPTCHA_PUBLIC_KEY = env("RECAPTCHA_PUBLIC_KEY", default="")
RECAPTCHA_PRIVATE_KEY = env("RECAPTCHA_PRIVATE_KEY", default="")
GOOGLE_MAPS_EMBED_API_KEY = env("GOOGLE_MAPS_EMBED_API_KEY", default="")

# Matomo (self-hosted analytics)
# ------------------------------------------------------------------------------
# MATOMO_URL is where Matomo is hosted (the analytics server, not the site URL);
# the tracked site is identified solely by MATOMO_SITE_ID. Hardcoded because it's
# a single self-hosted Matomo for a single site. MATOMO_ENABLED is tied to DEBUG
# (True locally, False in production), so tracking only runs in production.
MATOMO_URL = "https://analytics.yoolink.de"
MATOMO_SITE_ID = "1"
MATOMO_ENABLED = not DEBUG

YCMS_UPLOAD_LIMIT_BYTES = {
    "image": env.int("YCMS_IMAGE_UPLOAD_MAX_BYTES", default=100 * 1024 * 1024),
    "video": env.int("YCMS_VIDEO_UPLOAD_MAX_BYTES", default=800 * 1024 * 1024),
    "document": env.int("YCMS_DOCUMENT_UPLOAD_MAX_BYTES", default=150 * 1024 * 1024),
    "archive": env.int("YCMS_ARCHIVE_UPLOAD_MAX_BYTES", default=120 * 1024 * 1024),
    "subtitle": env.int("YCMS_SUBTITLE_UPLOAD_MAX_BYTES", default=10 * 1024 * 1024),
}

# TEMPLATES
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#templates
TEMPLATES = [
    {
        # https://docs.djangoproject.com/en/dev/ref/settings/#std:setting-TEMPLATES-BACKEND
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        # https://docs.djangoproject.com/en/dev/ref/settings/#dirs
        "DIRS": [str(APPS_DIR / "templates")],
        # https://docs.djangoproject.com/en/dev/ref/settings/#app-dirs
        "APP_DIRS": True,
        "OPTIONS": {
            # https://docs.djangoproject.com/en/dev/ref/settings/#template-context-processors
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.template.context_processors.i18n",
                "django.template.context_processors.media",
                "django.template.context_processors.static",
                "django.template.context_processors.tz",
                "django.contrib.messages.context_processors.messages",
                "yoolink.users.context_processors.allauth_settings",
                "yoolink.ycms.context_processors.user_settings_context",
                "yoolink.ycms.context_processors.cms_permissions_context",
                "yoolink.ycms.context_processors.notifications_context",
                "yoolink.ycms.context_processors.cms_language_context",
                "yoolink.ycms.context_processors.matomo_context",
            ],
        },
    }
]

# https://docs.djangoproject.com/en/dev/ref/settings/#form-renderer
FORM_RENDERER = "django.forms.renderers.TemplatesSetting"

# http://django-crispy-forms.readthedocs.io/en/latest/install.html#template-packs
CRISPY_TEMPLATE_PACK = "bootstrap5"
CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"

# FIXTURES
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#fixture-dirs
FIXTURE_DIRS = (str(APPS_DIR / "fixtures"),)

# SECURITY
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#session-cookie-httponly
SESSION_COOKIE_HTTPONLY = True
# https://docs.djangoproject.com/en/dev/ref/settings/#csrf-cookie-httponly
CSRF_COOKIE_HTTPONLY = True
# https://docs.djangoproject.com/en/dev/ref/settings/#secure-browser-xss-filter
SECURE_BROWSER_XSS_FILTER = True
# https://docs.djangoproject.com/en/dev/ref/settings/#x-frame-options
X_FRAME_OPTIONS = "DENY"

EMAIL_OWNER = 'yoolink@t-online.de'
DASHBOARD_URL = f"{SITE_BASE_URL}/"


# ADMIN
# ------------------------------------------------------------------------------
# Django Admin URL.
ADMIN_URL = "admin/"
# https://docs.djangoproject.com/en/dev/ref/settings/#admins
ADMINS = [("""Sebastian""", "yoolink@t-online.de")]
# https://docs.djangoproject.com/en/dev/ref/settings/#managers
MANAGERS = ADMINS

# LOGGING
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#logging
# See https://docs.djangoproject.com/en/dev/topics/logging for
# more details on how to customize your logging configuration.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "%(levelname)s %(asctime)s %(module)s "
            "%(process)d %(thread)d %(message)s"
        }
    },
    "handlers": {
        "console": {
            "level": "DEBUG",
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        }
    },
    "root": {"level": "INFO", "handlers": ["console"]},
}



# Celery
# ------------------------------------------------------------------------------
if USE_TZ:
    # https://docs.celeryq.dev/en/stable/userguide/configuration.html#std:setting-timezone
    CELERY_TIMEZONE = TIME_ZONE
# https://docs.celeryq.dev/en/stable/userguide/configuration.html#std:setting-broker_url
CELERY_BROKER_URL = env("CELERY_BROKER_URL")
# https://docs.celeryq.dev/en/stable/userguide/configuration.html#std:setting-result_backend
CELERY_RESULT_BACKEND = CELERY_BROKER_URL
# https://docs.celeryq.dev/en/stable/userguide/configuration.html#result-extended
CELERY_RESULT_EXTENDED = True
# https://docs.celeryq.dev/en/stable/userguide/configuration.html#result-backend-always-retry
# https://github.com/celery/celery/pull/6122
CELERY_RESULT_BACKEND_ALWAYS_RETRY = True
# https://docs.celeryq.dev/en/stable/userguide/configuration.html#result-backend-max-retries
CELERY_RESULT_BACKEND_MAX_RETRIES = 10
# https://docs.celeryq.dev/en/stable/userguide/configuration.html#std:setting-accept_content
CELERY_ACCEPT_CONTENT = ["json"]
# https://docs.celeryq.dev/en/stable/userguide/configuration.html#std:setting-task_serializer
CELERY_TASK_SERIALIZER = "json"
# https://docs.celeryq.dev/en/stable/userguide/configuration.html#std:setting-result_serializer
CELERY_RESULT_SERIALIZER = "json"
# https://docs.celeryq.dev/en/stable/userguide/configuration.html#task-time-limit
# TODO: set to whatever value is adequate in your circumstances
CELERY_TASK_TIME_LIMIT = 5 * 60
# https://docs.celeryq.dev/en/stable/userguide/configuration.html#task-soft-time-limit
# TODO: set to whatever value is adequate in your circumstances
CELERY_TASK_SOFT_TIME_LIMIT = 60
# https://docs.celeryq.dev/en/stable/userguide/configuration.html#beat-scheduler
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"
# https://docs.celeryq.dev/en/stable/userguide/configuration.html#worker-send-task-events
CELERY_WORKER_SEND_TASK_EVENTS = True
# https://docs.celeryq.dev/en/stable/userguide/configuration.html#std-setting-task_send_sent_event
CELERY_TASK_SEND_SENT_EVENT = True
# django-allauth
# ------------------------------------------------------------------------------
ACCOUNT_ALLOW_REGISTRATION = env.bool("DJANGO_ACCOUNT_ALLOW_REGISTRATION", True)
# https://docs.allauth.org/en/latest/account/configuration.html
ACCOUNT_LOGIN_METHODS = {"username"}
# https://docs.allauth.org/en/latest/account/configuration.html
ACCOUNT_SIGNUP_FIELDS = ["email*", "username*", "password1*", "password2*"]
# https://docs.allauth.org/en/latest/account/configuration.html
ACCOUNT_EMAIL_VERIFICATION = "mandatory"
# https://docs.allauth.org/en/latest/account/configuration.html
ACCOUNT_ADAPTER = "yoolink.users.adapters.AccountAdapter"
# https://django-allauth.readthedocs.io/en/latest/forms.html
ACCOUNT_FORMS = {"signup": "yoolink.users.forms.UserSignupForm"}
# https://docs.allauth.org/en/latest/socialaccount/configuration.html
SOCIALACCOUNT_ADAPTER = "yoolink.users.adapters.SocialAccountAdapter"
# https://django-allauth.readthedocs.io/en/latest/forms.html
SOCIALACCOUNT_FORMS = {"signup": "yoolink.users.forms.UserSocialSignupForm"}
# django-compressor
# ------------------------------------------------------------------------------
# https://django-compressor.readthedocs.io/en/latest/quickstart/#installation
INSTALLED_APPS += ["compressor", "modeltranslation"]
STATICFILES_FINDERS += ["compressor.finders.CompressorFinder"]
# django-rest-framework
# -------------------------------------------------------------------------------
# django-rest-framework - https://www.django-rest-framework.org/api-guide/settings/
REST_FRAMEWORK = {
    #DEFAULT_AUTHENTICATION_CLASSES": (
    #    "rest_framework.authentication.SessionAuthentication",
    #    "rest_framework.authentication.TokenAuthentication",
    #),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    # Nur JSON ausliefern. Die Browsable API (HTML-Oberfläche) wird in
    # local.py für die Entwicklung wieder aktiviert, ist in Produktion aber
    # bewusst deaktiviert, damit öffentliche Endpunkte keine REST-Oberfläche
    # mit Struktur/Formular offenlegen.
    "DEFAULT_RENDERER_CLASSES": ("rest_framework.renderers.JSONRenderer",),
}

# django-cors-headers - https://github.com/adamchainz/django-cors-headers#setup
CORS_URLS_REGEX = r"^/api/.*$"

# By Default swagger ui is available only to admin user(s). You can change permission classes to change that
# See more configuration options at https://drf-spectacular.readthedocs.io/en/latest/settings.html#settings
SPECTACULAR_SETTINGS = {
    "TITLE": "YooLink API",
    "DESCRIPTION": "Documentation of API endpoints of YooLink",
    "VERSION": "1.0.0",
    "SERVE_PERMISSIONS": ["rest_framework.permissions.IsAdminUser"],
}
# Your stuff...
# ------------------------------------------------------------------------------
SITE_ID = 1
