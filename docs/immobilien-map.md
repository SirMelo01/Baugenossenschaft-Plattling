# Dynamische Adressen auf der Objektkarte

Beim Anlegen oder Ändern einer Adresse im CMS ermittelt der Server die Position
über die **Google Geocoding API**. Die Koordinaten werden am Objekt gespeichert.
Die öffentliche Karte zeigt rote Standardmarker direkt an diesen Positionen;
Überlappungen beim Herauszoomen sind erlaubt. Sie führt keine Adresssuchen aus.
Es gibt keine fest hinterlegten Hausnummern oder Gebäudekoordinaten mehr.

Der Link „Route“ übergibt dagegen eine Adresse an die Google-Maps-Website.
Ein funktionierender Route-Link bestätigt deshalb weder die API-Freischaltung
noch die Konfiguration des Server-Schlüssels.

## Google Cloud und Serverkonfiguration

1. Im richtigen Cloud-Projekt **Geocoding API** aktivieren. Das Projekt benötigt
   eine aktive Abrechnung. Die **Geolocation API ist nicht erforderlich**.
2. Den bisherigen Browser-Schlüssel mit Website-Beschränkung für
   `https://bgsplattling.yoolink.de/*` und **Maps JavaScript API** beibehalten.
   Eventuell zusätzlich benötigte Maps Embed API ebenfalls beibehalten.
3. Einen separaten Server-Schlüssel erstellen:
   - API-Beschränkung: **Geocoding API**.
   - Anwendungsbeschränkung: **IP-Adressen**, öffentliche ausgehende IP des
     Produktionsservers (bei NAT die nach außen sichtbare IP, keine Docker-IP).
4. In `.envs/.production/.django` auf dem Server hinterlegen:

   ```dotenv
   GOOGLE_MAPS_GEOCODING_API_KEY=<separater Server-Schlüssel>
   GEOCODING_ENABLED=True
   ```

   Schlüssel nicht committen. Nach Änderung der Umgebung den Django-Container
   neu erstellen, damit er die neue Variable übernimmt; ein bloßer Prozessneustart
   aktualisiert die Container-Umgebung nicht:

   ```sh
   docker compose -f production.yml up -d --build django
   ```

Ein mit Websites/HTTP-Referrern beschränkter Schlüssel funktioniert für diese
REST-Anfragen vom Server nicht. Daher wird der Embed-Schlüssel nicht mehr als
Ersatz für einen fehlenden Server-Schlüssel verwendet.

Quellen: [Google: API einrichten](https://developers.google.com/maps/documentation/geocoding/guides-v3/get-api-key),
[Google: Schlüsselbeschränkungen](https://developers.google.com/maps/api-security-best-practices).

## Prüfen und bestehende Immobilien neu ermitteln

Auf dem Produktionsserver zuerst eine bisher fehlende Adresse testen. Der
Prüfbefehl verändert keine Immobilien:

```sh
docker compose -f production.yml exec django python manage.py geocode_immobilien --check-address "Dr.-Kiefl-Straße 35, 94447 Plattling"
```

Nach erfolgreicher Prüfung **beim Wechsel von der bisherigen festen Zuordnung**
die vorhandenen automatischen Koordinaten einmal neu ermitteln:

```sh
docker compose -f production.yml exec django python manage.py geocode_immobilien --force
```

Das ist nötig, weil die bisherige Sonderzuordnung nur die öffentliche Ausgabe
ersetzte und in der Datenbank noch alte oder fehlende Koordinaten stehen können.
Manuell gesetzte Positionen werden auch mit `--force` nicht überschrieben.
Ohne `--force` werden nur fehlende Koordinaten ergänzt. Mit `--address-contains`
kann der Lauf auf einen Straßennamen eingegrenzt werden.

Neue Immobilien brauchen danach keinen Befehl: Adresse eintragen und speichern.
Im CMS erlaubt „Automatisch bestimmen“ jederzeit eine erneute Suche.

## Treffer und Fehler

Straße, Hausnummer (auch Buchstabenzusätze und Bereiche) und angegebene PLZ
müssen zum Treffer passen. Google muss eine Gebäude- oder interpolierte
Hausnummernposition liefern; bloße Straßen-/Ortsmittelpunkte werden verworfen.
Gebäudepositionen werden bevorzugt. Bei einem Ortsteilzusatz wird bei Bedarf
zusätzlich ohne diesen gesucht. Google kann trotzdem nicht jede Adresse exakt
auflösen; für solche Fälle bleibt die manuelle Positionierung im CMS verfügbar.

Fehlender Schlüssel, abgelehnte API-Anfragen, Limits und Netzwerkfehler werden
im CMS konkret gemeldet. Die Immobilie lässt sich trotzdem speichern. Eine
vorhandene Position derselben Adresse bleibt bei Fehlern erhalten; nach einem
Adresswechsel werden keine alten Koordinaten für das neue Gebäude verwendet.
Der Warntext bleibt nach der Weiterleitung im CMS für den speichernden Benutzer
sichtbar. Ein erfolgreicher weiterer Speichervorgang ersetzt ihn.

## Tests

```sh
python -m unittest discover -s tests -p test_geocoding.py
python -m pytest tests/test_shop_safety_net.py -q
node --test tests/immobilien-map.test.cjs
```

Die HTTP-Antworten in den Tests sind simuliert. Die echte Freischaltung wird mit
`--check-address` vom freigegebenen Server aus geprüft. Die sichtbare Google-Karte
wird auf der freigegebenen Domain geprüft; localhost ist dafür nicht autorisiert.
