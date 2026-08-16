"""Setzt die Domain des django.contrib.sites-Eintrags auf die Kundendomain.

Migration 0003 hat die Domain einmalig auf yoolink.de gesetzt und ist in der
Produktionsdatenbank längst gelaufen - eine Änderung dort würde nichts mehr
bewirken. Deshalb hier eine eigene, idempotente Migration.

Die Domain bestimmt u.a. die Links in der Passwort-Reset-Mail und die absoluten
URLs in sitemap.xml. Sie kommt aus settings.SITE_DOMAIN, damit die Domain nur an
einer Stelle gepflegt werden muss.
"""
from django.conf import settings
from django.db import migrations

OLD_DOMAIN = "yoolink.de"
OLD_NAME = "YooLink"


def set_domain_forward(apps, schema_editor):
    Site = apps.get_model("sites", "Site")
    Site.objects.update_or_create(
        id=settings.SITE_ID,
        defaults={
            "domain": settings.SITE_DOMAIN,
            "name": "Baugenossenschaft Plattling eG",
        },
    )


def set_domain_backward(apps, schema_editor):
    Site = apps.get_model("sites", "Site")
    Site.objects.update_or_create(
        id=settings.SITE_ID,
        defaults={"domain": OLD_DOMAIN, "name": OLD_NAME},
    )


class Migration(migrations.Migration):

    dependencies = [("sites", "0004_alter_options_ordering_domain")]

    operations = [migrations.RunPython(set_domain_forward, set_domain_backward)]
