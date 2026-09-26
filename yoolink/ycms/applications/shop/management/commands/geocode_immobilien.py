"""Fehlende Koordinaten fuer bereits gepflegte Anschriften nachtragen.

Beim Speichern im CMS werden Koordinaten automatisch ermittelt. Immobilien, die
seither nicht bearbeitet wurden, haben aber noch keine - sie stehen dann nur in
der Liste neben der Objektkarte und nicht als Marker darauf. Dieser Befehl holt
das einmalig nach:

    python manage.py geocode_immobilien
"""

from django.core.management.base import BaseCommand

from yoolink.ycms.applications.shop.geocoding import coordinates_for_address, geocode_address
from yoolink.ycms.applications.shop.models import Product


class Command(BaseCommand):
    help = "Ermittelt fehlende Koordinaten zu den Adressen der Immobilien."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Auch Immobilien neu bestimmen, die bereits Koordinaten haben.",
        )
        parser.add_argument(
            "--address-contains",
            default="",
            help="Nur Anschriften mit diesem Straßennamen neu bestimmen.",
        )

    def handle(self, *args, **options):
        # Von Hand im CMS korrigierte Positionen fasst auch --force nicht an.
        products = Product.objects.exclude(address="").exclude(position_manual=True).order_by("title")
        if options["address_contains"]:
            products = products.filter(address__icontains=options["address_contains"])
        if not options["force"]:
            products = products.filter(latitude__isnull=True) | products.filter(longitude__isnull=True)

        found = 0
        missed = 0
        refreshed = {}

        for product in products.distinct():
            if options["force"]:
                # Eine zweite Wohnung derselben Anschrift darf keine alte,
                # falsche Position als vermeintlichen Treffer zurueckliefern.
                key = product.address.strip().casefold()
                if key not in refreshed:
                    refreshed[key] = geocode_address(product.address) or (None, None)
                latitude, longitude = refreshed[key]
            else:
                latitude, longitude = coordinates_for_address(
                    product.address, exclude_pk=product.pk, previous=product
                )

            if latitude is None or longitude is None:
                missed += 1
                if options["force"]:
                    Product.objects.filter(pk=product.pk).update(latitude=None, longitude=None)
                self.stdout.write(self.style.WARNING(f"Nicht gefunden: {product.title} - {product.address}"))
                continue

            Product.objects.filter(pk=product.pk).update(latitude=latitude, longitude=longitude)
            found += 1
            self.stdout.write(f"{product.title}: {latitude}, {longitude}")

        self.stdout.write(self.style.SUCCESS(f"{found} Immobilien verortet, {missed} ohne Treffer."))
