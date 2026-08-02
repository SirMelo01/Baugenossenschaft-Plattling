from django.apps import AppConfig


class CmsBlogApplicationConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "yoolink.ycms.applications.blog"
    label = "ycms_blog_application"
    verbose_name = "YooLink CMS Blog Application"

    def ready(self):
        from . import schema  # noqa: F401
