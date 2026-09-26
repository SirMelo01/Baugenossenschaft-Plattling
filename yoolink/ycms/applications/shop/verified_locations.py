"""Geprüfte Gebäudepositionen; Herkunft und Genauigkeit: docs/immobilien-map.md.

Nur vollständige, eindeutig passende Anschriften verwenden. Manuelle CMS-
Positionen haben Vorrang. Diese lokalen Daten benötigen keinen Geocoding-Dienst.
"""

import re


BUILDING_POSITIONS = {
    "31": (48.7836862, 12.8686252),
    "33": (48.7838371, 12.8686297),
    "33a": (48.7843550, 12.8683467),
    "33b": (48.7844882, 12.8683287),
}


def verified_position(address):
    normalized = " ".join((address or "").casefold().split())
    match = re.fullmatch(
        r"(?:dr\.?|doktor)[\s-]*kiefl[\s-]*(?:strasse|str\.?)\s+"
        r"(31|33[ab]?)\s*,\s*94447\s+plattling(?:[\s-]+höhenrain)?"
        r"(?:\s*,\s*(?:deutschland|germany))?",
        normalized,
    )
    return BUILDING_POSITIONS.get(match.group(1)) if match else None
