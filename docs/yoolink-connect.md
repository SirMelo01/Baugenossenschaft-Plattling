# YooLink Connect Integration

YooLink Connect ist ein browserbasierter Verbindungsflow fuer externe Plattformen. Die Plattform speichert keine YooLink-Zugangsdaten. Nutzer loggen sich im jeweiligen YooLink CMS ein, bestaetigen die Verbindung, und die Plattform tauscht danach einen kurzlebigen Authorization Code gegen einen Developer API Key.

Der Flow ist fuer mehrere YooLink-CMS-Instanzen gedacht. Die externe Anwendung muss nur die jeweilige CMS-URL kennen, zum Beispiel `https://kunde-a.de` oder `https://kunde-b.de`.

## Endpunkte pro CMS

Aus einer CMS-Base-URL werden diese Endpunkte gebildet:

```text
Authorize URL:
https://<cms-domain>/cms/settings/developer/connect/

Token Exchange URL:
https://<cms-domain>/api/connect/token/

API Ping:
https://<cms-domain>/api/ping/

Blog API:
https://<cms-domain>/api/cms/blog/

OpenAPI Schema:
https://<cms-domain>/api/schema/
```

## Sicherheit

YooLink Connect nutzt PKCE mit `S256`.

Die externe Plattform erzeugt vor dem Redirect:

- `code_verifier`: zufaelliger String mit 43 bis 128 Zeichen.
- `code_challenge`: `base64url(sha256(code_verifier))`.
- `state`: zufaelliger CSRF-Schutzwert.

Die Plattform speichert `code_verifier`, `state`, `cms_base_url` und `redirect_uri` serverseitig in einer Session oder kurzlebigen Datenbankzeile. Der API Key wird erst beim Token Exchange erzeugt und nur einmal zurueckgegeben.

## Authorize Request

Leite den Nutzer im Browser zu dieser URL:

```text
GET https://<cms-domain>/cms/settings/developer/connect/
  ?client_name=Meine%20KI%20Plattform
  &redirect_uri=https%3A%2F%2Fki.example.com%2Fapi%2Fyoolink%2Fcallback
  &scope=blog
  &access_level=write
  &state=<random-state>
  &code_challenge=<pkce-code-challenge>
  &code_challenge_method=S256
```

Parameter:

| Name | Pflicht | Beschreibung |
| --- | --- | --- |
| `client_name` | nein | Anzeigename der externen Anwendung. |
| `redirect_uri` | ja | Callback-URL deiner Plattform. Muss HTTPS sein. Lokal im YooLink DEBUG-Modus ist `http://localhost` erlaubt. |
| `scope` | nein | Aktuell `blog`. Mehrere Scopes koennen spaeter per Leerzeichen oder Komma gesendet werden. |
| `access_level` | nein | `read` oder `write`. Standard ist `read`. |
| `state` | empfohlen | Zufallswert, den du im Callback pruefst. |
| `code_challenge` | ja | PKCE Challenge. |
| `code_challenge_method` | ja | Muss `S256` sein. |

Nach Login, 2FA und Zustimmung leitet YooLink zur `redirect_uri` zurueck:

```text
https://ki.example.com/api/yoolink/callback?code=yl_connect_...&state=<random-state>
```

Bei Ablehnung:

```text
https://ki.example.com/api/yoolink/callback?error=access_denied&error_description=...&state=<random-state>
```

## Token Exchange

Dein Backend tauscht den Code gegen den API Key:

```http
POST https://<cms-domain>/api/connect/token/
Content-Type: application/json

{
  "grant_type": "authorization_code",
  "code": "yl_connect_...",
  "code_verifier": "<original-code-verifier>",
  "redirect_uri": "https://ki.example.com/api/yoolink/callback"
}
```

Erfolgreiche Antwort:

```json
{
  "token_type": "Bearer",
  "api_key": "yl_live_...",
  "base_url": "https://kunde.de/api/cms/",
  "ping_url": "https://kunde.de/api/ping/",
  "docs_url": "https://kunde.de/api/docs/",
  "schema_url": "https://kunde.de/api/schema/",
  "access_level": "write",
  "allowed_apps": ["blog"]
}
```

Speichere `api_key`, `base_url`, `ping_url`, `schema_url`, `access_level`, `allowed_apps` und die CMS-Domain verschluesselt oder in deinem Secret Store. Der `code` kann nur einmal verwendet werden und laeuft nach kurzer Zeit ab.

## API-Nutzung danach

```http
GET https://<cms-domain>/api/ping/
Authorization: Bearer yl_live_...
```

```http
GET https://<cms-domain>/api/cms/blog/
Authorization: Bearer yl_live_...
```

Die wichtigsten Blog-Workflows fuer KI-Plattformen sind in der separaten Detaildoku beschrieben:

- `docs/yoolink-blog-api.md`

Kurzfassung fuer die Einrichtung:

1. Nach dem Token Exchange `ping_url` aufrufen und die Verbindung pruefen.
2. Fuer Blog-Erstellung muss `access_level` den Wert `write` haben und `allowed_apps` muss `blog` enthalten.
3. Inhalte bevorzugt als `markdown` an `POST /api/cms/blog/` senden.
4. Bilder zuerst per `POST /api/cms/blog/media/` hochladen und danach das zurueckgegebene Markdown-Snippet in den Blog einfuegen.
5. Ein Titelbild bei JSON-Requests ueber `title_image_media_id` setzen, nicht als externe URL.
6. OpenAPI Schema fuer Client-Generatoren: `https://<cms-domain>/api/schema/`.
7. Swagger UI fuer Menschen und Tests im Browser: `https://<cms-domain>/api/docs/`.

Minimaler KI-Blog-Create:

```http
POST https://<cms-domain>/api/cms/blog/
Authorization: Bearer yl_live_...
Content-Type: application/json

{
  "title": "KI Event Rueckblick",
  "description": "Kurzer SEO-Teaser fuer Blogkarten und Meta Description.",
  "markdown": "## Rueckblick\n\nDer Event war stark besucht.",
  "active": true,
  "language": "de"
}
```

## Next.js Beispiel

### 1. PKCE Helper

```ts
function base64Url(buffer: ArrayBuffer) {
  return Buffer.from(buffer)
    .toString("base64")
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=+$/, "");
}

export function createCodeVerifier() {
  return base64Url(crypto.getRandomValues(new Uint8Array(48)).buffer);
}

export async function createCodeChallenge(verifier: string) {
  const data = new TextEncoder().encode(verifier);
  const digest = await crypto.subtle.digest("SHA-256", data);
  return base64Url(digest);
}
```

### 2. Connect starten

```ts
// app/api/yoolink/connect/route.ts
import { NextRequest, NextResponse } from "next/server";
import { createCodeChallenge, createCodeVerifier } from "@/lib/pkce";

export async function POST(request: NextRequest) {
  const { cmsBaseUrl } = await request.json();
  const normalizedBase = String(cmsBaseUrl).replace(/\/+$/, "");
  const redirectUri = `${process.env.APP_URL}/api/yoolink/callback`;
  const state = crypto.randomUUID();
  const codeVerifier = createCodeVerifier();
  const codeChallenge = await createCodeChallenge(codeVerifier);

  // In Produktion serverseitig in Session/DB speichern.
  // state -> { cmsBaseUrl: normalizedBase, codeVerifier, redirectUri }
  await savePendingYooLinkConnect({ state, cmsBaseUrl: normalizedBase, codeVerifier, redirectUri });

  const authorizeUrl = new URL(`${normalizedBase}/cms/settings/developer/connect/`);
  authorizeUrl.searchParams.set("client_name", "Meine KI Plattform");
  authorizeUrl.searchParams.set("redirect_uri", redirectUri);
  authorizeUrl.searchParams.set("scope", "blog");
  authorizeUrl.searchParams.set("access_level", "write");
  authorizeUrl.searchParams.set("state", state);
  authorizeUrl.searchParams.set("code_challenge", codeChallenge);
  authorizeUrl.searchParams.set("code_challenge_method", "S256");

  return NextResponse.json({ authorizeUrl: authorizeUrl.toString() });
}
```

### 3. Callback und Token Exchange

```ts
// app/api/yoolink/callback/route.ts
import { NextRequest, NextResponse } from "next/server";

export async function GET(request: NextRequest) {
  const url = new URL(request.url);
  const code = url.searchParams.get("code");
  const state = url.searchParams.get("state");
  const error = url.searchParams.get("error");

  if (!state) {
    return NextResponse.json({ error: "missing_state" }, { status: 400 });
  }

  const pending = await loadPendingYooLinkConnect(state);
  if (!pending) {
    return NextResponse.json({ error: "invalid_state" }, { status: 400 });
  }

  if (error) {
    return NextResponse.json({ error }, { status: 400 });
  }

  if (!code) {
    return NextResponse.json({ error: "missing_code" }, { status: 400 });
  }

  const tokenResponse = await fetch(`${pending.cmsBaseUrl}/api/connect/token/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      grant_type: "authorization_code",
      code,
      code_verifier: pending.codeVerifier,
      redirect_uri: pending.redirectUri,
    }),
  });

  const tokenData = await tokenResponse.json();
  if (!tokenResponse.ok) {
    return NextResponse.json(tokenData, { status: tokenResponse.status });
  }

  await saveYooLinkConnection({
    cmsBaseUrl: pending.cmsBaseUrl,
    apiKey: tokenData.api_key,
    baseUrl: tokenData.base_url,
    pingUrl: tokenData.ping_url,
    schemaUrl: tokenData.schema_url,
    accessLevel: tokenData.access_level,
    allowedApps: tokenData.allowed_apps,
  });
  await deletePendingYooLinkConnect(state);

  return NextResponse.redirect(`${process.env.APP_URL}/settings/integrations/yoolink?connected=1`);
}
```

## Verbindung testen

Nach dem Speichern des API Keys sollte die Plattform direkt `ping_url` aufrufen:

```ts
const response = await fetch(connection.pingUrl, {
  headers: {
    Authorization: `Bearer ${connection.apiKey}`,
  },
});

if (!response.ok) {
  throw new Error("YooLink Verbindung konnte nicht verifiziert werden.");
}
```

## Wiederverwendung fuer mehrere CMS-Projekte

Speichere pro Verbindung mindestens:

```json
{
  "cmsBaseUrl": "https://kunde.de",
  "apiKey": "yl_live_...",
  "baseUrl": "https://kunde.de/api/cms/",
  "pingUrl": "https://kunde.de/api/ping/",
  "schemaUrl": "https://kunde.de/api/schema/",
  "accessLevel": "write",
  "allowedApps": ["blog"]
}
```

Damit kann dieselbe KI-Plattform beliebig viele YooLink-CMS-Instanzen verbinden. Die Plattform muss keine projektspezifischen Endpunkte hart codieren, sondern baut sie aus der jeweiligen CMS-Base-URL oder nutzt die URLs aus der Token-Exchange-Antwort.
