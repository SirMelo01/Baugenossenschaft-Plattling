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

### Domain (Production)

**Aktuell live unter der Übergangs-Subdomain `bgsplattling.yoolink.de`.**
Die Kundendomain `baugenossenschaft-plattling.de` kommt später (siehe Umzug unten).

-   Einziger Schalter in Django ist `SITE_DOMAIN` in `config/settings/base.py`
    (per `DJANGO_SITE_DOMAIN` in der Env überschreibbar). Daraus leiten sich ab:
    `SITE_BASE_URL`, `ALLOWED_HOSTS`, `DASHBOARD_URL`, der www-Redirect
    (`yoolink/middleware.py`), die canonical-/OG-URLs in den Templates
    (`{{ site_base_url }}`) und das JSON-LD (`ycms/seo_schema.py`).
-   Separat gepflegt, weil außerhalb von Django: `compose/production/traefik/traefik.yml`
    (Host-Rules) und `compose/production/nginx/default.conf` (server_name).
-   Voraussetzung fürs Deployment: DNS-A-Record für `bgsplattling.yoolink.de` muss auf
    den Server zeigen, sonst schlägt die Let's-Encrypt-Challenge fehl.
-   Kein `www`-Host in Traefik: Für eine Subdomain gibt es weder DNS-Eintrag noch
    Zertifikat. Der www-Redirect in Django bleibt generisch und greift automatisch
    wieder, sobald `SITE_DOMAIN` eine Apex-Domain ist.
-   Die Domain des `django.contrib.sites`-Eintrags (Passwort-Reset-Mails, sitemap.xml)
    und `WebsiteSettings.website` (canonical/OG) setzen die Migrationen
    `sites.0005_set_site_domain_baugenossenschaft_plattling` und
    `ycms.0080_seed_baugenossenschaft_plattling_settings` aus `settings.SITE_DOMAIN`.
    Laufen mit dem normalen `migrate` mit.

#### Umzug auf die Kundendomain

Die beiden Migrationen oben sind Daten-Migrationen: Sie laufen **einmal**. Wenn
`SITE_DOMAIN` später geändert wird, müssen die zwei DB-Werte nachgezogen werden.

1.  `SITE_DOMAIN` in `config/settings/base.py` auf `baugenossenschaft-plattling.de`
    setzen (oder `DJANGO_SITE_DOMAIN` in `.envs/.production/.django`).
2.  Host-Regeln in `traefik.yml` (drei Router) und `nginx/default.conf` anpassen -
    dort dann wieder mit `www.`-Host, damit der 301 greifen kann.
3.  Neu bauen/starten und die zwei DB-Werte nachziehen:

        $ docker-compose -f production.yml run --rm django python manage.py shell -c "from django.conf import settings; from django.contrib.sites.models import Site; from yoolink.ycms.models import WebsiteSettings; Site.objects.update_or_create(id=settings.SITE_ID, defaults={'domain': settings.SITE_DOMAIN, 'name': 'Baugenossenschaft Plattling eG'}); w=WebsiteSettings.objects.order_by('id').first(); w.website=settings.SITE_BASE_URL; w.save()"

    `WebsiteSettings.website` lässt sich alternativ im CMS unter
    *Einstellungen -> Website-Daten* pflegen. Wichtig: **ohne** `www`, sonst zeigt
    canonical auf eine weiterleitende URL.

### Sprachen (aktuell: nur Deutsch)
-   Einziger Schalter ist `LANGUAGES` in `config/settings/base.py`. Dort steht aktuell
    nur `('de', _('Deutsch'))`. Daraus folgt automatisch:
    -   Sprachumschalter im CMS und auf der öffentlichen Seite werden ausgeblendet
    -   `i18n_patterns` erzeugt keine `/en/`-URLs mehr; alte `/en/...`-Links werden per
        301 auf die deutsche Seite umgeleitet (Regel am Ende von `config/urls.py`)
    -   ein englischer Browser bekommt trotzdem die deutsche Seite (`LocaleMiddleware`
        fällt auf `LANGUAGE_CODE = "de"` zurück)
    -   `/cms/set-language/en/` antwortet mit 400
-   Englisch wieder aktivieren: `('en', _('Englisch'))` in `LANGUAGES` ergänzen. Mehr ist
    nicht nötig - Umschalter, hreflang-Tags und `/en/`-Routen kommen von selbst zurück,
    die `/en/`-Redirect-Regel steht bewusst *nach* `i18n_patterns` und greift dann nicht mehr.

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
