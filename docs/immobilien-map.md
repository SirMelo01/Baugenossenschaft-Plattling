# Immobilienkarte mit dynamischer Adresssuche

## Ein Website-Schlüssel für Karte und Adresssuche

Das CMS ermittelt die Koordinaten beim Speichern **im Browser** über
`google.maps.Geocoder`. Dafür wird derselbe Website-Schlüssel verwendet wie für
die Karte (`GOOGLE_MAPS_JS_API_KEY`, standardmäßig `GOOGLE_MAPS_EMBED_API_KEY`).

Im Google-Cloud-Projekt und bei den API-Beschränkungen dieses Schlüssels müssen
**Maps JavaScript API** und **Geocoding API** freigegeben sein. Die Website-
Beschränkung muss die Produktionsdomain einschließlich CMS zulassen, z. B.
`https://bgsplattling.yoolink.de/*`. Das Projekt benötigt eine aktive Abrechnung.
Eine Geolocation API, ein zweiter Schlüssel oder eine Server-IP-Freigabe sind
für diesen Ablauf nicht erforderlich.

Quelle: [Google: Geocoding im Browser](https://developers.google.com/maps/documentation/javascript/geocoding).

## Ablauf im CMS

1. Immobilie anlegen oder bearbeiten, vollständige Adresse eintragen und speichern.
2. Das Formular wartet auf die Adresssuche. Straße, Hausnummer und angegebene PLZ
   müssen zum Ergebnis passen. Bloße Straßen-/Ortsmittelpunkte werden abgelehnt;
   Gebäude- und interpolierte Hausnummernpositionen sind zulässig, Gebäude bevorzugt.
   Bei Bedarf wird zusätzlich ohne den Ortsteilzusatz gesucht.
3. Der Browser übermittelt Koordinaten und die zugehörige Adresse mit dem Formular.
   Der Server prüft Zahlenwerte, Wertebereiche und Adresszuordnung und speichert
   die Position. Er führt bei CMS-Speichervorgängen keine Geocoding-Anfrage aus.
4. Die öffentliche Karte liest die gespeicherten Koordinaten und zeigt die roten
   Standardmarker. Überlappungen beim Herauszoomen sind erlaubt.

Pro geöffneter Formularseite werden erfolgreiche Suchen wiederverwendet. Nach
einem erneuten Öffnen und Speichern wird eine automatische Position neu ermittelt.
„Automatisch bestimmen“ erzwingt eine erneute Suche auch auf derselben Formularseite.
Ein von Hand gesetzter Pin bleibt erhalten, solange seine Adresse gleich bleibt;
„Automatisch bestimmen“ hebt diese Korrektur beim nächsten erfolgreichen Speichern auf.

**Bereits angelegte Immobilien ohne oder mit alten Koordinaten:** im CMS öffnen
und speichern. Bei einer manuellen Position zunächst „Automatisch bestimmen“ wählen.
Ein Server-Befehl ist dafür nicht nötig. Es gibt keine Sonderzuordnung für bestimmte
Hausnummern und keine fest hinterlegten Gebäudekoordinaten.

## Fehler

Fehlt eine API-Freigabe oder gibt es keinen passenden Hausnummerntreffer, wird
das im CMS angezeigt. Die Immobilie lässt sich trotzdem speichern. Eine bestehende
Position derselben Adresse bleibt erhalten; nach einem Adresswechsel wird kein
alter Pin für das neue Gebäude übernommen. Die Warnung bleibt nach der Weiterleitung
für den speichernden Benutzer sichtbar. Bei nicht eindeutig ermittelbaren Adressen
kann der Pin über „Pin prüfen / verschieben“ von Hand gesetzt werden.

„Route“ übergibt eine Adresse an die Google-Maps-Website. Ein funktionierender
Route-Link allein bestätigt weder die Freischaltung noch die Treffer der Geocoding API.

## Optionaler Server-Befehl

Der bestehende Management-Befehl `geocode_immobilien` ist weiterhin für Betreiber
verfügbar, die ausdrücklich Geocoding ohne Browser ausführen möchten. **Nur dieser
optionale Befehl** benötigt `GOOGLE_MAPS_GEOCODING_API_KEY` mit passenden Server-
Beschränkungen und `GEOCODING_ENABLED=True`. Er wird vom CMS nicht aufgerufen.

## Tests

```sh
node --test tests/product-geocoding.test.cjs tests/immobilien-map.test.cjs
python -m pytest tests/test_geocoding.py tests/test_shop_safety_net.py -q
```

Die Google-Antworten in den Tests sind simuliert. Die echte Kombination aus
Website-Schlüssel, CMS-Suche, Speichern und öffentlichen Markern wird auf der
freigegebenen Produktionsdomain geprüft. Localhost ist mit diesem Schlüssel
nicht freigegeben.
