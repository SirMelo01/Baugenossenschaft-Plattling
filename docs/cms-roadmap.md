# YooLink CMS Roadmap

Ziel: Das CMS soll für Kunden intuitiv bleiben, ohne zu einem freien Baukasten zu werden. YooLink liefert Design, Struktur und technische Basis aus; Kunden bearbeiten Inhalte, Medien, Produkte und Einstellungen innerhalb klarer Grenzen.

## Bereits erledigt

- Pricing- und Button-CMS-Views serverseitig hinter Login gelegt.
- CSRF-Ausnahmen bei Pricing-Löschung und Pricing-Reorder entfernt.
- Regressionstests für anonymen Zugriff und CSRF-Schutz ergänzt.
- Zentrale Upload-Grenzen pro Dateityp eingeführt und CMS-/API-Uploads daran angebunden.

## Phase 1: Sicherheitsbasis

1. Secrets aus dem Repo entfernen
   - Keine echten oder verwendbaren Access Keys als Defaults in Settings.
   - Alle Secrets nur über Environment-Variablen.
   - Alte/versehentlich committete Keys rotieren.

2. Zentrale Permission-Tests
   - Jede CMS-Mutationsroute anonym: Redirect/403.
   - Jede POST/DELETE/PATCH-Route mit CSRF-Checks.
   - Developer API getrennt testen: Bearer Auth, Scopes, expired/revoked keys.

3. HTML/CSS-Freiheiten einschränken
   - Freie Button-`css_classes` für normale Nutzer entfernen oder hinter Admin/Developer-Rolle verstecken.
   - Stattdessen Button-Presets: primary, secondary, outline, link, danger.
   - Privacy-/Blog-HTML nur mit Sanitizer oder erlaubten Blocktypen.

## Phase 2: Datenmodell für Kundenauslieferung

### Ein Kunde pro Deployment

Wenn wirklich jeder Kunde ein eigenes Repo, eigenes Backend, eigene Datenbank und eigenes Frontend bekommt, brauchst du kein volles Multi-Tenant-System. Dann ist die Datenbank selbst die harte Grenze. Das ist einfach, sicher und für kleine bis mittlere Kunden gut.

Trotzdem lohnt sich ein leichtes Site-/Owner-Modell:

- `SiteSettings` oder `WebsiteSettings` für öffentliche Website-Daten.
- User-spezifische Daten getrennt davon: Login, E-Mail, Profil, 2FA.
- Alle öffentlichen Daten wie Logo, Favicon, Firmenname, Adresse, SEO-Domain gehören zur Website, nicht zu einem beliebigen User.

Warum trotzdem sinnvoll:

- Mehruser-System wird einfacher.
- Tests und Datenimporte werden klarer.
- Später kann ein Backend mehrere Sites verwalten, ohne alles umzubauen.
- "Owner" ist dann eine Rolle, nicht automatisch der Datensatz, aus dem die Website ihre Daten liest.

### Mehrere Kunden in einer Instanz

Nur relevant, wenn ihr irgendwann ein zentrales YooLink-CMS für mehrere Kunden betreiben wollt. Dann braucht ihr harte Tenant-Grenzen:

- `Site`/`Tenant` Modell.
- Jede Content-, Medien-, Shop- und Settings-Tabelle bekommt `site`.
- Querysets filtern immer auf `request.site`.
- Medienpfade und API-Keys sind pro Site getrennt.

Empfehlung aktuell: kein komplettes Multi-Tenant-System bauen, aber `WebsiteSettings` und Rollen so modellieren, dass ihr später nicht festfahrt.

## Phase 3: Editor Boundaries

1. Presets statt freier Gestaltung
   - Farben aus Markenpalette.
   - Button-Typen statt CSS-Klassen.
   - Layout-Varianten pro Sektion, z.B. Bild links/rechts, Galerie kompakt/gross.
   - Keine freien neuen Sektionen für Kunden ohne Admin-Rolle.

2. Pricing CMS und Button-Erstellung verbessern
   - Pricing Cards im CMS visueller und näher an der echten Website-Darstellung bearbeiten.
   - Live Preview pro Pricing Card direkt im CMS.
   - Gesamt-Preview für den Pricing-Bereich mit Reihenfolge, aktiven/inaktiven Karten und Buttons.
   - Button-Erstellung intuitiver machen: Button-Text, Ziel, Typ, Icon und Verhalten statt freier CSS-Klassen.
   - Button-Presets mit klarer Vorschau: Primary, Secondary, Outline, Link, Call-to-Action.
   - Warnungen für problematische Buttons: leere URL, externer Link ohne neuen Tab, zu langer Text.
   - Pricing Features komfortabler bearbeiten: Drag & Drop, Inline-Validierung, leere Features verhindern.

3. Medienbibliothek professioneller machen
   - Alt-Text Pflicht oder zumindest Warnung.
   - Fokuspunkt/Crop für Bilder.
   - Verwendungsorte anzeigen: "Dieses Bild wird genutzt auf..."
   - Löschen blockieren oder warnen, wenn Medium noch verwendet wird.

4. Feldvalidierung kundennah machen
   - Empfohlene Textlängen für Hero, Karten, SEO.
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
   - Weitere Sprachen über Settings aktivierbar.
   - Public Language Switch zeigt nur aktivierte Sprachen.
   - Content-Fallback: wenn Sprache fehlt, Standard-Sprache anzeigen oder Seite als unvollständig markieren.

## Phase 5: Draft, Preview, Publish

Der aktuelle `Aktiv`-Button ist nicht dasselbe wie ein Draft-/Publish-Workflow.

`Aktiv` bedeutet typischerweise:

- Dieses Element ist öffentlich sichtbar oder nicht.
- Gut für Blogs, Produkte, Teammitglieder, Pricing Cards.
- Es verhindert aber nicht, dass Änderungen an einem bereits aktiven Element sofort live sind.

Draft/Publish bedeutet:

- Kunde kann eine aktive Seite bearbeiten, ohne die Live-Version sofort zu verändern.
- Änderungen landen zuerst in einem Entwurf.
- Kunde kann Preview anschauen.
- Erst "Veröffentlichen" ersetzt die Live-Version.
- "Verwerfen" setzt den Entwurf zurück.

Empfohlene erste Umsetzung:

- Nicht alles sofort versionieren.
- Erst für zentrale Seiteninhalte und Blog einführen.
- Produktdaten und Shop später, weil Lager/Preis/Bestellung transaktionaler sind.

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
   - UserSettings: Profil, Login-E-Mail, 2FA, persönliche Daten.
   - WebsiteSettings: Firmenname, Website-E-Mail, Adresse, Logo, Favicon, Domain, SEO Defaults.
   - Öffentliche Website liest nur aus WebsiteSettings.

4. Audit Log
   - Wer hat wann was geändert?
   - Alte Werte und neue Werte speichern.
   - Wiederherstellen für TextContent, Blog, Pricing, Produkte, Settings.

## Phase 7: Kundenkomfort

1. Dashboard als Aufgabenliste
   - Offene Bestellungen.
   - Neue Nachrichten.
   - Fehlende SEO-Texte.
   - Bilder ohne Alt-Text.
   - Unveröffentlichte Entwürfe.
   - Unvollständige Pricing Cards oder Buttons mit fehlenden Zielen.

2. Preview direkt im CMS
   - Seite in aktueller Sprache ansehen.
   - Mobile/Desktop Preview.
   - Draft Preview ohne öffentliche Veröffentlichung.
   - Pricing-Bereich und einzelne Cards direkt im CMS previewen.

3. Onboarding für Kunden
   - Kurze Checkliste: Logo, Firmeninfos, SEO, Bilder, Datenschutz, Shop.
   - Keine langen Erklärtexte im UI, sondern kontextnahe Hinweise.

4. Dokumentations-App im CMS
   - Neue CMS-App für eine durch Template/Library erzeugte Dokumentationsseite.
   - Inhalte nach YooLink-Versionen strukturieren, damit Kunden die passende Anleitung sehen.
   - Schritt-für-Schritt-Anleitungen für typische Aufgaben: Blog erstellen, Produkte pflegen, Medien hochladen, Pricing bearbeiten, SEO pflegen.
   - Suchfunktion und Kategorien für schnelle Hilfe direkt im CMS.
   - Dokumentation versionierbar halten, damit neue YooLink-Funktionen erklärt werden können, ohne alte Kunden-Setups zu verwirren.

## Empfohlene Reihenfolge

1. Security-Basis fertigstellen: Secrets und Permission-Tests.
2. `WebsiteSettings` einführen und öffentliche Website davon lesen lassen.
3. Freie CSS/HTML-Felder in Presets umbauen.
4. Pricing CMS und Button-Erstellung mit Preview neu strukturieren.
5. SEO-Settings pro Seite und Domain-Dynamik.
6. CMS-interne Dokumentations-App für versionierte Kundenhilfe.
7. Mehruser-Rollen und User-Verwaltung.
8. Audit Log und Wiederherstellung.
9. Draft/Preview/Publish für Seitencontent und Blog.
