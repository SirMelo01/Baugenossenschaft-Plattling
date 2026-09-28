"""Validate additional CMS addresses before saving the listing atomically."""
import json

from django.core.exceptions import ValidationError

from .geocoding import parse_manual_position
from .models import ProductAddress


def address_key(address):
    return " ".join(address.casefold().split())


def prepare_additional_addresses(raw, product, primary_address):
    # Old clients that do not send the field must not delete existing addresses.
    if raw is None:
        return None, []
    try:
        payload = json.loads(raw)
    except (ValueError, TypeError):
        raise ValidationError("Die zusätzlichen Adressen konnten nicht gelesen werden.")
    if not isinstance(payload, list):
        raise ValidationError("Die zusätzlichen Adressen müssen als Liste übermittelt werden.")
    existing = {address_key(item.address): item for item in product.additional_addresses.all()} if product.pk else {}
    seen = {address_key(primary_address)} if primary_address else set()
    rows, warnings = [], []
    for item in payload:
        if not isinstance(item, dict) or not isinstance(item.get("address"), str):
            raise ValidationError("Bitte für jede zusätzliche Adresse eine gültige Anschrift eintragen.")
        address = item["address"].strip()
        if not address or len(address) > 255:
            raise ValidationError("Jede zusätzliche Adresse muss zwischen 1 und 255 Zeichen enthalten.")
        key = address_key(address)
        if key in seen:
            raise ValidationError(f"Die Adresse „{address}“ wurde mehrfach eingetragen.")
        seen.add(key)
        old = existing.get(key)
        position = None
        manual = False
        if item.get("position_geocoded") is True:
            position = parse_manual_position(item.get("latitude"), item.get("longitude"))
            if not position or not isinstance(item.get("position_address"), str) or item["position_address"].strip() != address:
                raise ValidationError(f"Die ermittelte Position passt nicht zur Adresse „{address}“. Bitte erneut speichern.")
        # Preserve known coordinates only for the exact same address on failure.
        if old and old.latitude is not None and old.longitude is not None and (not position or old.position_manual):
            position = (old.latitude, old.longitude)
            manual = old.position_manual
        if item.get("position_geocoded") is not True and not manual:
            suffix = " Die bisherige Position bleibt erhalten." if position else " Bitte die Anschrift prüfen und erneut speichern."
            warnings.append(f"Adresse „{address}“ konnte nicht auf der Karte bestimmt werden.{suffix}")
        rows.append(ProductAddress(
            id=old.pk if old else None, product=product, address=address,
            latitude=position[0] if position else None,
            longitude=position[1] if position else None,
            position_manual=manual, sort_order=len(rows),
        ))
    return rows, warnings


def save_additional_addresses(product, rows):
    if rows is None:
        return
    product.additional_addresses.exclude(pk__in=[row.pk for row in rows if row.pk]).delete()
    for row in rows:
        row.product = product
        row.save()
    # A prefetched relation may still contain deleted or out-of-date rows.
    getattr(product, "_prefetched_objects_cache", {}).pop("additional_addresses", None)
