# YooLink Blog API fuer KI-Plattformen

Diese Datei beschreibt, wie eine externe KI-Plattform nach erfolgreicher YooLink-Connect-Einrichtung Blogs erstellt, aktualisiert und Medien hochlaedt.

Die Connect-Einrichtung steht in `docs/yoolink-connect.md`. Diese Datei beschreibt die Nutzung danach.

## Basis-URLs

Aus der verbundenen CMS-Domain entstehen diese URLs:

```text
CMS Base URL:
https://<cms-domain>

API Base URL:
https://<cms-domain>/api/

CMS API Base URL:
https://<cms-domain>/api/cms/

Blog Collection:
https://<cms-domain>/api/cms/blog/

Blog Detail:
https://<cms-domain>/api/cms/blog/{id}/

Blog Media Upload:
https://<cms-domain>/api/cms/blog/media/

Ping:
https://<cms-domain>/api/ping/

OpenAPI Schema:
https://<cms-domain>/api/schema/

Swagger UI:
https://<cms-domain>/api/docs/
```

Die Token-Exchange-Antwort liefert `base_url`, `ping_url`, `schema_url` und `docs_url` bereits fertig. Eine KI-Plattform sollte diese URLs speichern und nicht hart codieren.

## Authentifizierung

Alle Blog-Endpunkte brauchen einen YooLink Developer API Key.

Bevorzugt:

```http
Authorization: Bearer <api-key>
```

Alternativ:

```http
X-YooLink-API-Key: <api-key>
```

Ein `read` Key darf nur lesen. Ein `write` Key darf zusaetzlich erstellen, aktualisieren, loeschen und Medien hochladen.

Voraussetzungen fuer Blog-Erstellung:

- `access_level`: `write`
- `allowed_apps`: enthaelt `blog`

## Verbindung pruefen

Direkt nach dem Speichern des API Keys sollte die Plattform den Ping-Endpunkt aufrufen.

```http
GET https://<cms-domain>/api/ping/
Authorization: Bearer <api-key>
```

Beispielantwort:

```json
{
  "ok": true,
  "message": "YooLink Developer API ist erreichbar und authentifiziert.",
  "authenticated": true,
  "user": "cms-user@example.com",
  "access_level": "write",
  "allowed_apps": ["blog"]
}
```

## Blog-Endpunkte

| Methode | Endpoint | Zweck | Key |
| --- | --- | --- | --- |
| `GET` | `/api/cms/blog/` | Blogs listen | `read` oder `write` |
| `POST` | `/api/cms/blog/` | Blog erstellen | `write` |
| `GET` | `/api/cms/blog/{id}/` | Blog vollstaendig laden | `read` oder `write` |
| `PATCH` | `/api/cms/blog/{id}/` | Blog teilweise aktualisieren | `write` |
| `PUT` | `/api/cms/blog/{id}/` | Blog komplett ersetzen | `write` |
| `DELETE` | `/api/cms/blog/{id}/` | Blog loeschen | `write` |
| `POST` | `/api/cms/blog/media/` | Bild hochladen | `write` |

## Blogs listen

```http
GET https://<cms-domain>/api/cms/blog/?language=de&active=true&original_only=true&q=Event
Authorization: Bearer <api-key>
```

Query-Parameter:

| Name | Werte | Beschreibung |
| --- | --- | --- |
| `q` | String | Suche im Titel. |
| `language` | z. B. `de`, `en`, `fr` | Filtert nach Sprache. |
| `active` | `true`, `false`, `1`, `0`, `yes`, `no` | Filtert nach veroeffentlichten oder inaktiven Blogs. |
| `original_only` | `true`, `false`, `1`, `0`, `yes`, `no` | Nur Original-Blogs ohne Sprachvarianten. |

Die Liste ist bewusst kompakt. Sie enthaelt kein `markdown`, `body`, `code` und keine `translations`. Fuer vollstaendige Daten `GET /api/cms/blog/{id}/` verwenden.

Beispielantwort:

```json
[
  {
    "id": 12,
    "title": "Event Rueckblick",
    "slug": "event-rueckblick",
    "description": "Kurzer SEO-Teaser.",
    "active": true,
    "language": "de",
    "original": null,
    "title_image_url": "https://kunde.de/media/yoolink/blogs/12/title.png",
    "absolute_url": "https://kunde.de/blog/12-event-rueckblick/",
    "api_url": "https://kunde.de/api/cms/blog/12/",
    "date": "2026-05-10",
    "last_updated": "2026-05-10"
  }
]
```

## Blog erstellen

Fuer KI-Workflows ist `markdown` der empfohlene Inhaltstyp. YooLink erzeugt daraus automatisch:

- `body` als HTML fuer die Ausgabe
- `code` als Blog-Builder-Struktur fuer das CMS

```http
POST https://<cms-domain>/api/cms/blog/
Authorization: Bearer <write-api-key>
Content-Type: application/json
```

```json
{
  "title": "KI Event Rueckblick",
  "description": "Kurzer SEO-Teaser fuer Blogkarten und Meta Description.",
  "markdown": "## Rueckblick\n\nDer Event war stark besucht.\n\n- Punkt eins\n- Punkt zwei",
  "active": true,
  "language": "de"
}
```

Wichtige Felder:

| Feld | Pflicht | Typ | Beschreibung |
| --- | --- | --- | --- |
| `title` | ja | String | Blogtitel. Darf nicht leer sein. |
| `description` | ja | String | Kurzbeschreibung fuer Blogkarten, SEO und Meta Description. Darf nicht leer sein. |
| `markdown` | bedingt | String | Empfohlener Inhalt fuer KI-Workflows. Entweder `markdown`, `body` oder `code` muss gesetzt sein. |
| `body` | bedingt | HTML String | Alternative fuer vorhandenes HTML. YooLink erzeugt daraus Markdown und Builder-Code. |
| `code` | bedingt | JSON Array/Object | Interne Blog-Builder-Struktur. YooLink erzeugt daraus HTML und Markdown. |
| `active` | nein | Boolean | `true` veroeffentlicht den Blog, `false` speichert ihn als Entwurf. Standard im Modell ist `false`. |
| `language` | nein | String | `de`, `en` oder `fr`. Standard ist `de`. |
| `original` | nein | Integer/null | ID des Original-Blogs, wenn eine Sprachvariante erstellt wird. |
| `title_image_media_id` | nein | Integer | ID aus `POST /api/cms/blog/media/` fuer ein Titelbild bei JSON-Requests. |
| `title_image` | nein | Datei | Nur bei Multipart-Requests direkt an `/api/cms/blog/` oder `/api/cms/blog/{id}/`. |

Read-only Felder in Antworten:

- `id`
- `slug`
- `author`
- `absolute_url`
- `title_image_url`
- `translations`
- `date`
- `last_updated`

Beispielantwort:

```json
{
  "id": 12,
  "title": "KI Event Rueckblick",
  "slug": "ki-event-rueckblick",
  "description": "Kurzer SEO-Teaser fuer Blogkarten und Meta Description.",
  "body": "<h2>Rueckblick</h2><p>Der Event war stark besucht.</p>",
  "markdown": "## Rueckblick\n\nDer Event war stark besucht.",
  "code": [
    {
      "name": "title-1",
      "type": "h2",
      "value": "Rueckblick"
    },
    {
      "name": "textArea",
      "type": "p",
      "value": "<p>Der Event war stark besucht.</p>"
    }
  ],
  "active": true,
  "language": "de",
  "original": null,
  "author": "cms-user@example.com",
  "title_image": null,
  "title_image_url": "",
  "absolute_url": "https://kunde.de/blog/12-ki-event-rueckblick/",
  "translations": [
    {
      "id": 12,
      "title": "KI Event Rueckblick",
      "language": "de",
      "active": true,
      "is_current": true,
      "is_original": true,
      "api_url": "https://kunde.de/api/cms/blog/12/",
      "absolute_url": "https://kunde.de/blog/12-ki-event-rueckblick/"
    }
  ],
  "date": "2026-05-10",
  "last_updated": "2026-05-10"
}
```

## Bilder fuer Blog-Inhalte hochladen

Content-Bilder fuer Markdown-Blogs sollten zuerst ueber den Media-Endpunkt hochgeladen werden.

```http
POST https://<cms-domain>/api/cms/blog/media/
Authorization: Bearer <write-api-key>
Content-Type: multipart/form-data

file: event.png
title: Event Bild
alt_text: Volles Haus beim Event
```

Erlaubte Dateiendungen:

- `.jpg`
- `.jpeg`
- `.png`
- `.gif`
- `.webp`

Beispielantwort:

```json
{
  "id": 44,
  "title": "Event Bild",
  "alt_text": "Volles Haus beim Event",
  "url": "https://kunde.de/media/yoolink/files/event.png",
  "markdown": "![Volles Haus beim Event](https://kunde.de/media/yoolink/files/event.png)",
  "html": "<img src=\"https://kunde.de/media/yoolink/files/event.png\" alt=\"Volles Haus beim Event\" class=\"rounded-2xl my-4\">"
}
```

Die KI-Plattform kann `markdown` direkt in den Blog-Inhalt einfuegen:

```json
{
  "title": "Blog mit Bild",
  "description": "Beschreibung mit Bild.",
  "markdown": "## Galerie\n\n![Volles Haus beim Event](https://kunde.de/media/yoolink/files/event.png)",
  "title_image_media_id": 44,
  "active": true,
  "language": "de"
}
```

Wichtig: Bei JSON-Requests kann `title_image` keine externe URL sein. Fuer Titelbilder immer `title_image_media_id` verwenden oder den Blog als Multipart mit `title_image` senden.

## Blog aktualisieren

Teilupdate:

```http
PATCH https://<cms-domain>/api/cms/blog/12/
Authorization: Bearer <write-api-key>
Content-Type: application/json

{
  "active": false,
  "description": "Aktualisierte Beschreibung."
}
```

Wenn `markdown` aktualisiert wird, rendert YooLink `body` und `code` erneut:

```json
{
  "markdown": "## Neue Fassung\n\nAktualisierter Inhalt."
}
```

## Sprachvarianten

Ein Blog ohne `original` ist ein Original-Blog. Eine Uebersetzung referenziert das Original ueber `original`.

```http
POST https://<cms-domain>/api/cms/blog/
Authorization: Bearer <write-api-key>
Content-Type: application/json

{
  "title": "Event Review",
  "description": "English teaser.",
  "markdown": "## Review\n\nThe event was well attended.",
  "language": "en",
  "original": 12,
  "active": false
}
```

Pro Original darf jede Sprache nur einmal existieren. Wenn fuer ein Original bereits eine `en`-Variante existiert, gibt die API `400` zurueck.

## OpenAPI und Swagger

YooLink stellt eine maschinenlesbare OpenAPI-Spezifikation und eine Swagger UI bereit:

```text
OpenAPI JSON/YAML Schema:
https://<cms-domain>/api/schema/

Swagger UI:
https://<cms-domain>/api/docs/
```

Das OpenAPI Schema wird von `drf-spectacular` erzeugt und enthaelt die YooLink-Developer-Key-Authentifizierung als Security Scheme `YooLinkDeveloperApiKey`.

Fuer Client-Generatoren:

```bash
openapi-generator-cli generate \
  -i https://<cms-domain>/api/schema/ \
  -g typescript-fetch \
  -o ./src/generated/yoolink
```

Auch wenn ein generierter Client verwendet wird, sollte die Plattform den API Key als Header setzen:

```http
Authorization: Bearer <api-key>
```

oder:

```http
X-YooLink-API-Key: <api-key>
```

## Empfohlener Ablauf fuer KI-Plattformen

1. User gibt CMS-Domain ein, z. B. `https://kunde.de`.
2. Plattform startet YooLink Connect mit `scope=blog` und `access_level=write`.
3. User bestaetigt im YooLink CMS.
4. Plattform tauscht `code` plus `code_verifier` gegen `api_key`.
5. Plattform speichert `api_key`, `base_url`, `ping_url`, `schema_url`, `docs_url`, `access_level`, `allowed_apps`.
6. Plattform ruft `GET /api/ping/` auf.
7. KI erstellt Artikelentwurf als Markdown.
8. KI laedt benoetigte Bilder ueber `POST /api/cms/blog/media/` hoch.
9. KI setzt Bild-Markdown in den Artikel und optional `title_image_media_id`.
10. Plattform erstellt den Blog ueber `POST /api/cms/blog/`.
11. Plattform zeigt `absolute_url` und `api_url` aus der Antwort an.

## JavaScript-Beispiele

Verbindung testen:

```ts
async function pingYooLink(connection: { pingUrl: string; apiKey: string }) {
  const response = await fetch(connection.pingUrl, {
    headers: {
      Authorization: `Bearer ${connection.apiKey}`,
    },
  });

  if (!response.ok) {
    throw new Error("YooLink Verbindung konnte nicht verifiziert werden.");
  }

  return response.json();
}
```

Blog per Markdown erstellen:

```ts
async function createYooLinkBlog(connection: { cmsBaseUrl: string; apiKey: string }) {
  const response = await fetch(`${connection.cmsBaseUrl}/api/cms/blog/`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${connection.apiKey}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      title: "KI Event Rueckblick",
      description: "Kurzer SEO-Teaser fuer Blogkarten und Meta Description.",
      markdown: "## Rueckblick\n\nDer Event war stark besucht.",
      active: true,
      language: "de",
    }),
  });

  const data = await response.json();
  if (!response.ok) {
    throw new Error(`YooLink Blog konnte nicht erstellt werden: ${JSON.stringify(data)}`);
  }

  return data;
}
```

Bild hochladen:

```ts
async function uploadYooLinkBlogImage(
  connection: { cmsBaseUrl: string; apiKey: string },
  file: File,
) {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("title", "Event Bild");
  formData.append("alt_text", "Volles Haus beim Event");

  const response = await fetch(`${connection.cmsBaseUrl}/api/cms/blog/media/`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${connection.apiKey}`,
    },
    body: formData,
  });

  const data = await response.json();
  if (!response.ok) {
    throw new Error(`YooLink Bild konnte nicht hochgeladen werden: ${JSON.stringify(data)}`);
  }

  return data;
}
```

## Fehlercodes

| Status | Bedeutung |
| --- | --- |
| `400` | Validierungsfehler, z. B. fehlender Titel, leere Beschreibung, doppelte Sprachvariante oder falscher Upload-Typ. |
| `401` | API Key fehlt, ist ungueltig, abgelaufen oder widerrufen. |
| `403` | API Key hat nicht den Scope `blog` oder nur `read`, obwohl ein Schreibzugriff versucht wurde. |
| `404` | Blog-ID existiert nicht. |

## Hinweise fuer KI-generierte Inhalte

- Immer `title` und `description` setzen.
- Markdown bevorzugen, weil YooLink daraus automatisch HTML und Builder-Bloecke erzeugt.
- `active: false` verwenden, wenn der Artikel erst geprueft werden soll.
- `active: true` nur setzen, wenn die Plattform direkt veroeffentlichen darf.
- Fuer Bilder zuerst `/api/cms/blog/media/` verwenden und das `markdown` aus der Antwort in den Artikel einfuegen.
- Die Antwort nach `POST /api/cms/blog/` enthaelt `absolute_url` fuer die oeffentliche Seite und `id` fuer spaetere Updates.
