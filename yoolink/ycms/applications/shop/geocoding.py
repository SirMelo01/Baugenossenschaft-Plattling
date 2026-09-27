"""Anschriften in Koordinaten uebersetzen - einmal beim Speichern, nicht bei jedem Aufruf.

Gepflegt wird eine getippte Anschrift, die Objektkarte braucht aber Koordinaten.
Das Umrechnen kostet pro Anfrage Geld und Zeit, deshalb passiert es serverseitig
beim Speichern im CMS und das Ergebnis bleibt am Objekt stehen. Der Browser eines
Besuchers geocodiert nichts - sonst zahlte jeder Seitenaufruf die Adressen erneut.

Die Google Geocoding API wird mit einem eigenen Server-Key angesprochen.
Konfigurationsfehler werden dem CMS gemeldet, statt unbemerkt auf einen anderen
Dienst oder feste Adresszuordnungen zurueckzufallen.
"""

import json
import logging
import re
import unicodedata
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.conf import settings

logger = logging.getLogger(__name__)

GOOGLE_GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"
REQUEST_TIMEOUT_SECONDS = 6


class GeocodingError(Exception):
    """Actionable service/configuration error; safe to show in the CMS."""

    def __init__(self, code, message):
        self.code = code
        super().__init__(message)


def _address_parts(address):
    # German street addresses, including suffixes, ranges and omitted commas.
    match = re.match(
        r"^\s*(.+?)\s+(\d+(?:\s*[a-zA-Z])?(?:\s*[-/]\s*\d+\s*[a-zA-Z]?)?)"
        r"\s*(?:,|\s+(?=\d{5}\b)|$)", address or ""
    )
    if not match:
        return None, None
    return match.group(1), re.sub(r"\s+", "", match.group(2)).lower()


def _street_key(value):
    value = unicodedata.normalize("NFKD", (value or "").casefold())
    value = "".join(character for character in value if not unicodedata.combining(character))
    value = re.sub(r"^dr\.?", "doktor", value)
    value = re.sub(r"stra(?:sse|ße)|str\.?", "str", value)
    return re.sub(r"[^a-z0-9]", "", value)


def _matches_house(address, street, number):
    expected_street, expected_number = _address_parts(address)
    if expected_number is None:
        return False
    return (
        (number or "").replace(" ", "").lower() == expected_number
        and _street_key(street) == _street_key(expected_street)
    )


def _queries_for_address(address):
    # Ortsteil-Zusaetze wie "Plattling-Hoehenrain" verschlechtern die Suche
    # manchmal, obwohl die Postleitzahl und der Ort eindeutig sind.
    simplified = re.sub(r"(\b\d{5}\s+[^,\-]+)-[^,]+", r"\1", address)
    return [address] if simplified == address else [address, simplified]


def _fetch_json(url, params, headers=None):
    request = Request(f"{url}?{urlencode(params)}", headers=headers or {})
    with urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
        return json.loads(response.read().decode("utf-8"))


def _coordinates_from_google(address):
    api_key = settings.GOOGLE_MAPS_GEOCODING_API_KEY
    if not api_key:
        raise GeocodingError("MISSING_KEY", "Der Server-Schlüssel GOOGLE_MAPS_GEOCODING_API_KEY fehlt. "
                             "Bitte einen Schlüssel für die Google Geocoding API hinterlegen.")

    payload = _fetch_json(
        GOOGLE_GEOCODE_URL,
        {"address": address, "key": api_key, "region": "de", "language": "de", "components": "country:DE"},
    )
    status = payload.get("status")
    if status == "ZERO_RESULTS":
        return None
    if status != "OK":
        messages = {
            "REQUEST_DENIED": "Google lehnt die Adresssuche ab. Bitte Geocoding API, Abrechnung und "
                              "Server-Schlüssel prüfen (Server-IP statt Website-Beschränkung).",
            "OVER_DAILY_LIMIT": "Google meldet ein Abrechnungs-, Schlüssel- oder Tageslimitproblem bei der Adresssuche.",
            "OVER_QUERY_LIMIT": "Das Google-Limit für die Adresssuche ist erreicht. Bitte später erneut versuchen.",
        }
        raise GeocodingError(status or "INVALID_RESPONSE", messages.get(
            status, "Die Google-Adresssuche ist derzeit nicht verfügbar. Bitte später erneut versuchen."
        ))

    postcode = re.search(r"\b(\d{5})\b", address)
    matches = []
    for result in payload.get("results", []):
        components = {kind: item.get("long_name", "") for item in result.get("address_components", [])
                      for kind in item.get("types", [])}
        if not _matches_house(address, components.get("route"), components.get("street_number")):
            continue
        if postcode and components.get("postal_code") != postcode.group(1):
            continue
        geometry = result.get("geometry") or {}
        precision = geometry.get("location_type")
        if precision not in ("ROOFTOP", "RANGE_INTERPOLATED"):
            continue  # A street/city centre must never masquerade as a house.
        location = geometry.get("location") or {}
        position = parse_manual_position(location.get("lat"), location.get("lng"))
        if position:
            matches.append((precision != "ROOFTOP", position))
    # Prefer an actual building point over an interpolated house-number position.
    return sorted(matches)[0][1] if matches else None


def geocode_address(address):
    """Resolve any supported address dynamically; None means no house match.

    Service/configuration failures raise GeocodingError so the CMS can distinguish
    a disabled API from an address that Google does not know.
    """
    address = (address or "").strip()
    if not address:
        return None
    if not settings.GEOCODING_ENABLED:
        raise GeocodingError("DISABLED", "Die automatische Adresssuche ist deaktiviert (GEOCODING_ENABLED).")
    if _address_parts(address)[1] is None:
        return None

    for query in _queries_for_address(address):
        try:
            position = _coordinates_from_google(query)
        except GeocodingError:
            raise
        except (URLError, OSError, ValueError, KeyError, IndexError, TypeError, AttributeError) as error:
            # Never log request URLs or raw exception messages containing API keys.
            logger.warning("Google-Geocoding fehlgeschlagen (%s)", type(error).__name__)
            raise GeocodingError("SERVICE_UNAVAILABLE", "Die Google-Adresssuche konnte nicht erreicht werden "
                                 "oder hat ungültige Daten geliefert. Bitte erneut versuchen.") from None
        if position is not None:
            return position
    return None


def parse_manual_position(latitude, longitude):
    """Von Hand gesetzte Koordinaten aus dem CMS-Formular oder ``None``.

    Akzeptiert werden nur Werte, die tatsaechlich auf der Erde liegen - ein
    verrutschter oder leerer Wert soll auf das Geocoding zurueckfallen, statt
    einen Marker in den Atlantik zu setzen.
    """
    try:
        lat = float(str(latitude).replace(",", "."))
        lng = float(str(longitude).replace(",", "."))
    except (TypeError, ValueError):
        return None

    if not (-90 <= lat <= 90 and -180 <= lng <= 180) or (lat == 0 and lng == 0):
        return None
    return round(lat, 7), round(lng, 7)


def coordinates_for_address(address, exclude_pk=None, previous=None):
    """Koordinaten fuer eine Anschrift, ohne unnoetige Anfragen.

    Drei Faelle kommen ohne Netzwerk aus: keine Anschrift, eine unveraenderte
    Anschrift mit bereits bekannten Koordinaten und eine Anschrift, die schon an
    einer anderen Immobilie haengt. Der letzte Fall ist der Normalfall in einer
    Wohnanlage - mehrere Objekte unter derselben Hausnummer.
    """
    from yoolink.ycms.applications.shop.models import Product

    address = (address or "").strip()
    if not address:
        return None, None

    if previous is not None:
        known_address = (previous.address or "").strip()
        if known_address == address and previous.latitude is not None and previous.longitude is not None:
            if previous.position_manual:
                return previous.latitude, previous.longitude

    # Eine von Hand korrigierte Position im selben Haus schlaegt jede berechnete.
    twin = (
        Product.objects.filter(address__iexact=address, latitude__isnull=False, longitude__isnull=False)
        .exclude(pk=exclude_pk)
        .order_by("-position_manual", "pk")
        .values_list("latitude", "longitude", "position_manual")
        .first()
    )
    if twin and twin[2]:
        return twin[0], twin[1]

    if previous is not None and (previous.address or "").strip() == address:
        if previous.latitude is not None and previous.longitude is not None:
            return previous.latitude, previous.longitude
    if twin:
        return twin[0], twin[1]

    position = geocode_address(address)
    if position is None:
        return None, None

    return position
