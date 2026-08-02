# YooLink

Wie ich alles aufgesetzt habe und gehostet habe:
https://www.youtube.com/watch?v=DLxcyndCvO4


-   Docker wird benutzt und deshalb muss vor allen Befehlen stehen: ()
## Local:

### Webseite starten:
        $ docker-compose -f local.yml build
        $ docker-compose -f local.yml up

### Load Translations:
        - {% load i18n %}
        - {% trans "FAQ_TITLE" %}
        $ docker-compose -f local.yml run --rm django python manage.py makemessages -l de -l en
        $ docker-compose -f local.yml run --rm django python manage.py compilemessages

### Django Migrations:
        $ docker-compose -f local.yml run --rm django python manage.py makemigrations
        $ docker-compose -f local.yml run --rm django python manage.py migrate 

### App erstellen:
        $ docker-compose -f local.yml run --rm django python manage.py startapp namederapp

### Superuser erstellen:
        $ docker-compose -f local.yml run --rm django python manage.py createsuperuser

### File Compress:
        $ docker-compose -f local.yml run --rm django python manage.py collectstatic
        $ docker-compose -f local.yml run --rm django python manage.py compress --force

## Production:
        $ in der Console erst mal in Ordner YooLink gehen: cd YooLink/

### Webseite starten:
        $ docker-compose -f production.yml build
        $ docker-compose -f production.yml up

### Django Migrations:
        $ docker-compose -f production.yml run --rm django python manage.py makemigrations
        $ docker-compose -f production.yml run --rm django python manage.py migrate

-   Migration `0079_strip_language_suffix_from_blog_slugs` (Blog) und
    `shop.0008_strip_language_suffix_from_product_slugs` (Produkte) entfernen bei
    bestehenden Übersetzungen automatisch das alte Sprach-Suffix im Slug
    (z. B. "-en"). Laufen mit dem normalen `migrate` mit, sind idempotent und
    vorsichtig: sie benennen nur um, wenn der Ziel-Slug frei ist. Alte URLs
    bleiben erreichbar und werden per 301 auf die neue kürzere URL weitergeleitet
    (die pk bleibt gleich). Bei Blogs und Produkten ändert sich der Slug ab jetzt
    nicht mehr automatisch bei Titeländerungen.

### Superuser erstellen:
        $ docker-compose -f production.yml run --rm django python manage.py createsuperuser
        $ bestehender Superuser:

### File Compress:
        $ docker-compose -f production.yml run --rm django python manage.py collectstatic
        $ docker-compose -f production.yml run --rm django python manage.py compress --force


### Load Translations Production:
        $ docker-compose -f production.yml run --rm django python manage.py makemessages -l de -l en
        $ docker-compose -f production.yml run --rm django python manage.py compilemessages

### .django Manuell kopieren:
-   da wichtige Schlüssel in der Datei liegen, müssen diese per Hand kopiert werden

        $ cd .envs/
        $ cd .production/
        $ nano .django 

### Recovery Backups:
-   Anleitung für lokale Downloads, automatische verschlüsselte Remote-Backups, Env-Variablen und Restore:

        docs/yoolink-recovery-backups.md

### Konsole verlassen:
        $ exit




## Tailwind:
        $ npm run build
        $ npm run watch

## Tests / Sicherheitsnetz:

### Lokal alle Tests ausführen:
        $ docker-compose -f local.yml run --rm django pytest

### Lokal nur CMS-/Shop-Sicherheitsnetz ausführen:
        $ docker-compose -f local.yml run --rm django pytest tests/test_cms_2fa.py tests/test_cms_core_modules.py tests/test_shop_safety_net.py tests/test_public_pages_safety_net.py

### Lokal mit frischer Testdatenbank:
        $ docker-compose -f local.yml run --rm django pytest --create-db

### Production-Check vor Deployment:
-   Nicht gegen die echte Produktionsdatenbank testen. Vorher eine separate Test-Env oder Staging-Env nutzen.
-   Das Production-Image enthält keine lokalen Test-Dependencies wie pytest. Deshalb vor dem Deployment das komplette Test-Sicherheitsnetz lokal/CI ausführen und das Production-Image separat mit Django Checks prüfen:

        $ docker-compose -f local.yml run --rm django pytest
        $ docker-compose -f production.yml run --rm django python manage.py check --deploy --settings=config.settings.production

### Prompt für Codex vor Updates:
        Analysiere die anstehenden Dependency-Updates. Führe zuerst das komplette Test-Sicherheitsnetz lokal aus, behebe Regressionen in kleinen Schritten und fasse danach zusammen, welche CMS-, Shop-, Auth-, Medien- und Public-Page-Flows grün sind.

## Externe YooLink API

Developer API Keys werden im CMS unter `Einstellungen -> Developer Settings` erstellt. Der vollständige Schlüssel wird nur direkt nach dem Erstellen angezeigt und danach nur gehasht gespeichert.

### Blog API

Basis-Endpoint:

        /api/cms/blog/

Authentifizierung:

        Authorization: Bearer <api-key>

Read-only Keys dürfen `GET` verwenden. Write Keys dürfen zusätzlich `POST`, `PATCH`, `PUT` und `DELETE` verwenden.

`GET /api/cms/blog/` liefert eine kompakte Liste ohne `markdown`, `body`, `code` und Sprachvarianten. Vollständige Blogdaten inklusive Markdown, HTML-Body und Sprachvarianten gibt es über `GET /api/cms/blog/<id>/`.

Minimaler JSON-Body zum Erstellen eines Blogs:

        {
          "title": "Event Rückblick",
          "description": "Kurzer SEO-Teaser für Blogkarten und Meta Description.",
          "markdown": "## Rückblick\n\nMarkdown-Inhalt des automatisch generierten Blogartikels.",
          "active": true,
          "language": "de"
        }

Alternativ kann weiterhin `body` als HTML oder `code` als Blog-Builder-JSON gesendet werden. Die API erzeugt daraus automatisch Markdown, damit KI-Workflows eine klare Textquelle haben.

Content-Bilder für Markdown-Blogs können per Multipart direkt hochgeladen werden:

        POST /api/cms/blog/media/
        Authorization: Bearer <write-api-key>
        Content-Type: multipart/form-data

        file: event.png
        title: Event Bild
        alt_text: Volles Haus beim Event

Die Antwort enthält `url`, `markdown` und `html`. Für KI-Workflows reicht es meist, das `markdown`-Snippet direkt in den Blog-Markdown einzusetzen. Ein Titelbild kann beim Erstellen oder Aktualisieren eines Blogs weiterhin als Multipart-Feld `title_image` an `/api/cms/blog/` bzw. `/api/cms/blog/<id>/` gesendet werden.

Wenn du den Blog als JSON erstellst, kann `title_image` keine URL sein. Lade das Bild vorher über `/api/cms/blog/media/` hoch und sende danach die erhaltene `id` als `title_image_media_id`:

        {
          "title": "Event Rückblick",
          "description": "Kurzer SEO-Teaser für Blogkarten und Meta Description.",
          "markdown": "## Rückblick\n\nMarkdown-Inhalt.",
          "title_image_media_id": 44,
          "active": true,
          "language": "de"
        }

## Deployment

https://www.youtube.com/watch?v=DLxcyndCvO4 hier ab minute 28

ssh root@195.201.112.17


## Fehlerbehebung Space full
df -h
docker system df

docker buildx prune -af
docker builder prune -af
docker image prune -af
docker container prune -f

docker compose -f production.yml build --no-cache django
docker compose -f production.yml up
