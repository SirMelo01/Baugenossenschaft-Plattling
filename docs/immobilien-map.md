# Gebäudepositionen der Objektkarte

Die öffentliche Karte verwendet gespeicherte bzw. lokal geprüfte Koordinaten.
Sie benötigt die Maps JavaScript API, aber **keine Geocoding API im Browser**.
Manuelle Positionen aus dem CMS haben Vorrang vor den lokalen Gebäudepositionen.

## Dr.-Kiefl-Straße 31, 33, 33a und 33b

Am 27.09.2026 anhand der beschrifteten Gebäude in der amtlichen Parzellarkarte
geprüft. Der bisherige automatische Punkt (48.784648, 12.869245) war ein
Straßenpunkt, kein Treffer für diese Hausnummern. Nominatim lieferte für diese
Anschriften nur Straßen ohne passende Hausnummer zurück.

Quelle: **Bayerische Vermessungsverwaltung**, [ALKIS-Parzellarkarte](https://www.ldbv.bayern.de/produkte/liegenschaftsinformationen/parzellarkarte.html),
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/deed.de).
Die Koordinaten wurden aus der Karte abgeleitet (Änderung gegenüber der Quelle).
Es sind Positionen innerhalb des jeweiligen beschrifteten Gebäudeteils, keine
vermessenen Hauseingänge. Die Nachkommastellen bedeuten keine Zentimetergenauigkeit.

| Hausnummer | Breitengrad | Längengrad | Referenzpixel x/y |
| --- | --- | --- | --- |
| 31 | 48.7836862 | 12.8686252 | 562 / 825 |
| 33 | 48.7838371 | 12.8686297 | 563 / 774 |
| 33a | 48.7843550 | 12.8683467 | 500 / 599 |
| 33b | 48.7844882 | 12.8683287 | 496 / 554 |

Reproduzierbare Referenz: WMS `https://geoservices.bayern.de/od/wms/alkis/v1/parzellarkarte`,
`SERVICE=WMS`, `VERSION=1.1.1`, `REQUEST=GetMap`,
`LAYERS=by_alkis_parzellarkarte_farbe`, `STYLES=`, `SRS=EPSG:3857`,
`BBOX=1432247.800293882,6237949.349741135,1432797.800293882,6238649.349741135`,
`WIDTH=1100`, `HEIGHT=1400`, `FORMAT=image/png`.
Pixelkoordinaten ab links oben; Auflösung 0,5 projizierte Meter/Pixel.
Umrechnung nach WGS84 mit inverser Web-Mercator-Projektion.

Die Zuordnung gilt ausschließlich für diese Hausnummern, Straße und PLZ/Ort.
Sie wird bei der öffentlichen Ausgabe auch für alte oder fehlende automatische
Daten verwendet und beim nächsten Speichern übernommen. Ein erneutes Geocoding
oder eine zusätzliche Google-Freischaltung ist dafür nicht erforderlich.

## Marker

Jedes Objekt hat einen klassischen roten Google-Marker direkt an seiner
Gebäudeposition. Beim Herauszoomen dürfen sich die Marker überlappen. Es gibt
keine Verschiebung, Verbindungslinien oder Cluster. Über „Auf Karte zeigen“ in
der Liste lässt sich jedes Objekt gezielt öffnen, auch bei identischen Positionen.

## Prüfung

```text
node --test tests/immobilien-map.test.cjs
python -m unittest discover -s tests -p test_verified_locations.py
python -m pytest tests/test_shop_safety_net.py -q
```

Die lokalen Regressionstests prüfen Koordinatenzuordnung, unveränderte Positionen beim Zoom und Auswahl
mit simulierten Maps-Objekten ohne Geocoder. Sie ersetzen keinen Produktionstest:
der Google-Key ist auf die Produktionsdomain beschränkt. Nach Veröffentlichung
auf `/immobilien/` mit Einwilligung für externe Medien die vier Gebäude, Zoom,
Listenfokus und Popups kontrollieren. Es darf keine Geocoding-Anfrage entstehen.
