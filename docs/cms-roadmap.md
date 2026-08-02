# YooLink CMS Roadmap

Ziel: Das CMS soll fuer Kunden intuitiv bleiben, ohne zu einem freien Baukasten zu werden. YooLink liefert Design, Struktur und technische Basis aus; Kunden bearbeiten Inhalte, Medien, Produkte und Einstellungen innerhalb klarer Grenzen.

## Bereits erledigt

- Pricing- und Button-CMS-Views serverseitig hinter Login gelegt.
- CSRF-Ausnahmen bei Pricing-Loeschung und Pricing-Reorder entfernt.
- Regressionstests fuer anonymen Zugriff und CSRF-Schutz ergaenzt.
- Zentrale Upload-Grenzen pro Dateityp eingefuehrt und CMS-/API-Uploads daran angebunden.

## Phase 1: Sicherheitsbasis

1. Secrets aus dem Repo entfernen
   - Keine echten oder verwendbaren Access Keys als Defaults in Settings.
   - Alle Secrets nur ueber Environment-Variablen.
   - Alte/versehentlich committete Keys rotieren.

2. Zentrale Permission-Tests
   - Jede CMS-Mutationsroute anonym: Redirect/403.
   - Jede POST/DELETE/PATCH-Route mit CSRF-Checks.
   - Developer API getrennt testen: Bearer Auth, Scopes, expired/revoked keys.

3. HTML/CSS-Freiheiten einschraenken
   - Freie Button-`css_classes` fuer normale Nutzer entfernen oder hinter Admin/Developer-Rolle verstecken.
   - Stattdessen Button-Presets: primary, secondary, outline, link, danger.
   - Privacy-/Blog-HTML nur mit Sanitizer oder erlaubten Blocktypen.

## Phase 2: Datenmodell fuer Kundenauslieferung

### Ein Kunde pro Deployment

Wenn wirklich jeder Kunde ein eigenes Repo, eigenes Backend, eigene Datenbank und eigenes Frontend bekommt, brauchst du kein volles Multi-Tenant-System. Dann ist die Datenbank selbst die harte Grenze. Das ist einfach, sicher und fuer kleine bis mittlere Kunden gut.

Trotzdem lohnt sich ein leichtes Site-/Owner-Modell:

- `SiteSettings` oder `WebsiteSettings` fuer oeffentliche Website-Daten.
- User-spezifische Daten getrennt davon: Login, E-Mail, Profil, 2FA.
- Alle oeffentlichen Daten wie Logo, Favicon, Firmenname, Adresse, SEO-Domain gehoeren zur Website, nicht zu einem beliebigen User.

Warum trotzdem sinnvoll:

- Mehruser-System wird einfacher.
- Tests und Datenimporte werden klarer.
- Spaeter kann ein Backend mehrere Sites verwalten, ohne alles umzubauen.
- "Owner" ist dann eine Rolle, nicht automatisch der Datensatz, aus dem die Website ihre Daten liest.

### Mehrere Kunden in einer Instanz

Nur relevant, wenn ihr irgendwann ein zentrales YooLink-CMS fuer mehrere Kunden betreiben wollt. Dann braucht ihr harte Tenant-Grenzen:

- `Site`/`Tenant` Modell.
- Jede Content-, Medien-, Shop- und Settings-Tabelle bekommt `site`.
- Querysets filtern immer auf `request.site`.
- Medienpfade und API-Keys sind pro Site getrennt.

Empfehlung aktuell: kein komplettes Multi-Tenant-System bauen, aber `WebsiteSettings` und Rollen so modellieren, dass ihr spaeter nicht festfahrt.

## Phase 3: Editor Boundaries

1. Presets statt freier Gestaltung
   - Farben aus Markenpalette.
   - Button-Typen statt CSS-Klassen.
   - Layout-Varianten pro Sektion, z.B. Bild links/rechts, Galerie kompakt/gross.
   - Keine freien neuen Sektionen fuer Kunden ohne Admin-Rolle.

2. Pricing CMS und Button-Erstellung verbessern
   - Pricing Cards im CMS visueller und naeher an der echten Website-Darstellung bearbeiten.
   - Live Preview pro Pricing Card direkt im CMS.
   - Gesamt-Preview fuer den Pricing-Bereich mit Reihenfolge, aktiven/inaktiven Karten und Buttons.
   - Button-Erstellung intuitiver machen: Button-Text, Ziel, Typ, Icon und Verhalten statt freier CSS-Klassen.
   - Button-Presets mit klarer Vorschau: Primary, Secondary, Outline, Link, Call-to-Action.
   - Warnungen fuer problematische Buttons: leere URL, externer Link ohne neuen Tab, zu langer Text.
   - Pricing Features komfortabler bearbeiten: Drag & Drop, Inline-Validierung, leere Features verhindern.

3. Medienbibliothek professioneller machen
   - Alt-Text Pflicht oder zumindest Warnung.
   - Fokuspunkt/Crop fuer Bilder.
   - Verwendungsorte anzeigen: "Dieses Bild wird genutzt auf..."
   - Loeschen blockieren oder warnen, wenn Medium noch verwendet wird.

4. Feldvalidierung kundennah machen
   - Empfohlene Textlaengen fuer Hero, Karten, SEO.
   - URL-Validierung mit klaren Meldungen.
   - Zeit-/Preis-/Boolean-Logik aus Views in Forms/Services ziehen.

## Phase 4: SEO und Sprachen

1. SEO pro Seite editierbar machen
   - Seitentitel.
   - Meta Description.
   - Canonical URL.
   - OG/Twitter Bild.
   - Index/Noindex.
   - Social Preview im CMS.

2. Domain aus Settings statt hart verdrahtet
   - `site_url` in WebsiteSettings.
   - Canonical, OG URLs, API-Doku und E-Mail-Links daraus bauen.

3. Sprachen dynamischer machen
   - Deutsch und Englisch bleiben Pflicht/Default.
   - Weitere Sprachen ueber Settings aktivierbar.
   - Public Language Switch zeigt nur aktivierte Sprachen.
   - Content-Fallback: wenn Sprache fehlt, Standard-Sprache anzeigen oder Seite als unvollstaendig markieren.

## Phase 5: Draft, Preview, Publish

Der aktuelle `Aktiv`-Button ist nicht dasselbe wie ein Draft-/Publish-Workflow.

`Aktiv` bedeutet typischerweise:

- Dieses Element ist oeffentlich sichtbar oder nicht.
- Gut fuer Blogs, Produkte, Teammitglieder, Pricing Cards.
- Es verhindert aber nicht, dass Aenderungen an einem bereits aktiven Element sofort live sind.

Draft/Publish bedeutet:

- Kunde kann eine aktive Seite bearbeiten, ohne die Live-Version sofort zu veraendern.
- Aenderungen landen zuerst in einem Entwurf.
- Kunde kann Preview anschauen.
- Erst "Veroeffentlichen" ersetzt die Live-Version.
- "Verwerfen" setzt den Entwurf zurueck.

Empfohlene erste Umsetzung:

- Nicht alles sofort versionieren.
- Erst fuer zentrale Seiteninhalte und Blog einfuehren.
- Produktdaten und Shop spaeter, weil Lager/Preis/Bestellung transaktionaler sind.

## Phase 6: Mehruser-System und Audit

1. Rollenmodell
   - Owner: Nutzer verwalten, WebsiteSettings, API-Keys, alles.
   - Editor: Seiten, Blog, Medien.
   - Shop Manager: Produkte, Bestellungen.
   - Support/Viewer: lesen, Notifications, keine destruktiven Aktionen.
   - Developer: API-Keys, technische Einstellungen.

2. User-Verwaltung im CMS
   - Owner kann Nutzer einladen/anlegen.
   - Passwort-Reset und 2FA pro User.
   - Rollen pro Website vergeben.

3. Settings richtig trennen
   - UserSettings: Profil, Login-E-Mail, 2FA, persoenliche Daten.
   - WebsiteSettings: Firmenname, Website-E-Mail, Adresse, Logo, Favicon, Domain, SEO Defaults.
   - Oeffentliche Website liest nur aus WebsiteSettings.

4. Audit Log
   - Wer hat wann was geaendert?
   - Alte Werte und neue Werte speichern.
   - Wiederherstellen fuer TextContent, Blog, Pricing, Produkte, Settings.

## Phase 7: Kundenkomfort

1. Dashboard als Aufgabenliste
   - Offene Bestellungen.
   - Neue Nachrichten.
   - Fehlende SEO-Texte.
   - Bilder ohne Alt-Text.
   - Unveroeffentlichte Entwuerfe.
   - Unvollstaendige Pricing Cards oder Buttons mit fehlenden Zielen.

2. Preview direkt im CMS
   - Seite in aktueller Sprache ansehen.
   - Mobile/Desktop Preview.
   - Draft Preview ohne oeffentliche Veroeffentlichung.
   - Pricing-Bereich und einzelne Cards direkt im CMS previewen.

3. Onboarding fuer Kunden
   - Kurze Checkliste: Logo, Firmeninfos, SEO, Bilder, Datenschutz, Shop.
   - Keine langen Erklaertexte im UI, sondern kontextnahe Hinweise.

4. Dokumentations-App im CMS
   - Neue CMS-App fuer eine durch Template/Library erzeugte Dokumentationsseite.
   - Inhalte nach YooLink-Versionen strukturieren, damit Kunden die passende Anleitung sehen.
   - Schritt-fuer-Schritt-Anleitungen fuer typische Aufgaben: Blog erstellen, Produkte pflegen, Medien hochladen, Pricing bearbeiten, SEO pflegen.
   - Suchfunktion und Kategorien fuer schnelle Hilfe direkt im CMS.
   - Dokumentation versionierbar halten, damit neue YooLink-Funktionen erklaert werden koennen, ohne alte Kunden-Setups zu verwirren.

## Empfohlene Reihenfolge

1. Security-Basis fertigstellen: Secrets und Permission-Tests.
2. `WebsiteSettings` einfuehren und oeffentliche Website davon lesen lassen.
3. Freie CSS/HTML-Felder in Presets umbauen.
4. Pricing CMS und Button-Erstellung mit Preview neu strukturieren.
5. SEO-Settings pro Seite und Domain-Dynamik.
6. CMS-interne Dokumentations-App fuer versionierte Kundenhilfe.
7. Mehruser-Rollen und User-Verwaltung.
8. Audit Log und Wiederherstellung.
9. Draft/Preview/Publish fuer Seitencontent und Blog.
