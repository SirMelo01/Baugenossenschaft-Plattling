"""Anschriften in Koordinaten uebersetzen - einmal beim Speichern, nicht bei jedem Aufruf.

Gepflegt wird eine getippte Anschrift, die Objektkarte braucht aber Koordinaten.
Das Umrechnen kostet pro Anfrage Geld und Zeit, deshalb passiert es serverseitig
beim Speichern im CMS und das Ergebnis bleibt am Objekt stehen. Der Browser eines
Besuchers geocodiert nichts - sonst zahlte jeder Seitenaufruf die Adressen erneut.

Google ist die erste Wahl, weil die Karte ohnehin von Google kommt und dieselbe
Schreibweise dort am zuverlaessigsten gefunden wird. Ist die Geocoding API fuer
den Key nicht freigeschaltet, springt Nominatim (OpenStreetMap) ein: sonst bliebe
die Karte leer, obwohl alle Anschriften gepflegt sind.
"""

import json
import logging
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.conf import settings

logger = logging.getLogger(__name__)

GOOGLE_GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"
NOMINATIM_GEOCODE_URL = "https://nominatim.openstreetmap.org/search"
# Nominatim verlangt einen sprechenden User-Agent, sonst wird die Anfrage abgewiesen.
NOMINATIM_USER_AGENT = "BaugenossenschaftPlattling/1.0 (+https://www.baugenossenschaft-plattling.de)"
REQUEST_TIMEOUT_SECONDS = 6


def _fetch_json(url, params, headers=None):
    request = Request(f"{url}?{urlencode(params)}", headers=headers or {})
    with urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
        return json.loads(response.read().decode("utf-8"))


def _coordinates_from_google(address):
    api_key = settings.GOOGLE_MAPS_GEOCODING_API_KEY
    if not api_key:
        return None

    payload = _fetch_json(
        GOOGLE_GEOCODE_URL,
        {"address": address, "key": api_key, "region": "de", "language": "de"},
    )

    if payload.get("status") != "OK":
        # ZERO_RESULTS heisst: Adresse unbekannt. Alles andere (REQUEST_DENIED bei
        # nicht freigeschalteter API, OVER_QUERY_LIMIT) ist ein Konfigurations- oder
        # Kontingentproblem und gehoert ins Log, damit es auffindbar bleibt.
        if payload.get("status") != "ZERO_RESULTS":
            logger.warning(
                "Google-Geocoding fuer %r fehlgeschlagen: %s %s",
                address,
                payload.get("status"),
                payload.get("error_message", ""),
            )
        return None

    location = payload["results"][0]["geometry"]["location"]
    return float(location["lat"]), float(location["lng"])


def _coordinates_from_nominatim(address):
    payload = _fetch_json(
        NOMINATIM_GEOCODE_URL,
        {"q": address, "format": "json", "limit": "1", "countrycodes": "de"},
        headers={"User-Agent": NOMINATIM_USER_AGENT, "Accept": "application/json"},
    )

    if not payload:
        return None

    return float(payload[0]["lat"]), float(payload[0]["lon"])


def geocode_address(address):
    """Koordinaten zu einer Anschrift oder ``None``, wenn sie nicht gefunden wird.

    Ein Fehlschlag darf das Speichern im CMS nie verhindern - die Immobilie steht
    dann eben nur in der Liste neben der Karte und nicht als Marker darauf.
    """
    address = (address or "").strip()
    if not address or not settings.GEOCODING_ENABLED:
        return None

    for resolve in (_coordinates_from_google, _coordinates_from_nominatim):
        try:
            position = resolve(address)
        except (URLError, OSError, ValueError, KeyError, IndexError, TypeError) as error:
            logger.warning("Geocoding fuer %r fehlgeschlagen: %s", address, error)
            continue

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
            return previous.latitude, previous.longitude

    # Eine von Hand korrigierte Position im selben Haus schlaegt jede berechnete.
    twin = (
        Product.objects.filter(address__iexact=address, latitude__isnull=False, longitude__isnull=False)
        .exclude(pk=exclude_pk)
        .order_by("-position_manual", "pk")
        .values_list("latitude", "longitude")
        .first()
    )
    if twin:
        return twin

    position = geocode_address(address)
    if position is None:
        return None, None

    return position
