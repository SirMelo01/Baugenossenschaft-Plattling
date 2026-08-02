# YooLink Blog Markdown Guidelines

Diese Guidelines sind für externe KI-Tools gedacht, die YooLink nicht kennen und trotzdem Blog-Inhalte erzeugen sollen, die im CMS-Editor und über die Blog-API sauber funktionieren.

## Ziel

Erzeuge den eigentlichen Blog-Inhalt als Markdown. Titel, Kurzbeschreibung/SEO-Description, Sprache, Aktiv-Status und Titelbild sind eigene CMS- oder API-Felder und gehören nicht als Frontmatter in den Markdown-Text.

Empfohlene Ausgabe:

```json
{
  "title": "Klarer Blogtitel",
  "description": "Kurzer SEO-Teaser für Blogkarten und Meta Description.",
  "markdown": "## Einstieg\n\nDer eigentliche Artikeltext..."
}
```

Für Copy-Paste ins CMS reicht nur der Inhalt aus `markdown`.

## SEO-Regeln

- Nutze im Markdown kein `#`. Der Blogtitel ist das H1-Feld des CMS.
- Starte mit `##`, danach `###` und `####` für Unterabschnitte.
- Die `description` soll eine echte Meta Description sein: konkret, lesbar und meistens 140 bis 160 Zeichen lang.
- Wiederhole den Blogtitel nicht als ersten Satz.
- Schreibe pro Abschnitt kurze, scanbare Absätze.
- Nutze interne Links mit aussagekräftigem Linktext, nicht "hier klicken".
- Bilder brauchen einen beschreibenden Alt-Text.
- Videos brauchen einen klaren Titel; CMS-Videos sollten auch Alt-Text/Beschreibung haben.
- Verwende bevorzugt CMS-Medien unter `/media/...` statt externer Platzhalter-URLs.
- Füge keine kaputten Quellen, nicht erreichbaren Bildplatzhalter oder komplette HTML-Seiten ein.

## Unterstützte Elemente

| Builder-Element | Markdown |
| --- | --- |
| Titel I | `## Abschnitt` |
| Titel II | `### Unterabschnitt` |
| Titel III | `#### Detailabschnitt` |
| Text | Absätze, Listen, Links, `**fett**`, `*kursiv*`, `inline code`, Zitate (`> …`), sowie Inline-Auszeichnungen via HTML (siehe unten) |
| Bild | `![Alt-Text](/media/yoolink/images/bild.jpg){width=100% height=auto}` |
| Galerie | `:::gallery{height=420px}` mit Bildzeilen |
| YouTube | `::youtube{url=https://youtu.be/... title="Video Titel" width=100% height=315px}` |
| CMS Video | `::video{src=/media/.../video.mp4 poster=/media/.../poster.jpg title="Video Titel" alt="Beschreibung" controls preload=metadata width=100% height=420px}` |
| Datei | `::file{href=/media/.../guide.pdf title="Guide herunterladen" ext=.pdf}` |
| Code | fenced code blocks wie ```html |

## Standard-Markdown

### Überschriften

```markdown
## Hauptabschnitt

### Unterabschnitt

#### Detailabschnitt
```

### Absätze, Listen und Links

```markdown
Ein Absatz mit zwei bis vier Sätzen. Er soll scanbar bleiben und einen klaren Gedanken vermitteln.

- Punkt eins
- Punkt zwei
- Punkt drei

Weitere Informationen gibt es auf [der Kontaktseite](/kontakt/).
```

Vermeide verschachtelte Listen, Tabellen und stark komplexe Markdown-Strukturen, wenn der Inhalt später im CMS weiterbearbeitet werden soll.

### Zitate

```markdown
> Ein hervorgehobenes Zitat. Jede Zeile beginnt mit "> ".
```

### Inline-Auszeichnungen (Farbe, hoch-/tiefgestellt, unterstrichen …)

Diese Auszeichnungen kennt Markdown nicht – sie werden als **einfaches Inline-HTML**
geschrieben und bleiben beim Hin- und Herwechseln zwischen Builder und Markdown
sowie beim Speichern/Anzeigen vollständig erhalten:

```markdown
H<sub>2</sub>O, E = mc<sup>2</sup>
<u>unterstrichen</u> und <s>durchgestrichen</s>
<span style="color: rgb(230, 0, 0)">farbiger Text</span>
<span style="background-color: #fff3cd">hervorgehoben</span>
<mark>markiert</mark>
```

Aus Sicherheitsgründen werden bei `<span>` nur `color` und `background-color`
übernommen; erlaubte Inline-Tags sind `sub`, `sup`, `u`, `s`/`del`, `mark`, `br`.

### Bilder

Bilder stehen am besten als eigene Zeile:

```markdown
![Beschreibender Alt-Text](/media/yoolink/images/beispielbild.jpeg)
```

Optionale Größenangaben:

```markdown
![Beschreibender Alt-Text](/media/yoolink/images/beispielbild.jpeg){width=50%}
![Beschreibender Alt-Text](/media/yoolink/images/beispielbild.jpeg){width=640px height=auto}
```

Unterstützt werden `px`, `%`, `rem`, `em`, `vw`, `vh`, `auto` und `0`. Zahlen ohne Einheit werden als Pixel interpretiert.

Im CMS-Markdown-Editor kann ein Bild über den Bild-Dialog hochgeladen oder aus der Mediathek eingefügt werden. Für API-Workflows Bilder zuerst über `POST /api/cms/blog/media/` hochladen und das Feld `markdown` aus der Antwort in den Artikel einsetzen.

### Galerien

```markdown
:::gallery{width=100% height=420px}
![Erstes Bild](/media/yoolink/images/bild-1.jpeg)
![Zweites Bild](/media/yoolink/images/bild-2.jpeg)
![Drittes Bild](/media/yoolink/images/bild-3.jpeg)
:::
```

Der CMS-Markdown-Dialog kann vorhandene CMS-Galerien auswählen und als Galerieblock einfügen. Technisch wird die Galerie als Liste von Bild-URLs gespeichert, damit Markdown, HTML und Builder-Code synchron bleiben.

### YouTube

```markdown
::youtube{url=https://youtu.be/dQw4w9WgXcQ title="Produktvideo" width=100% height=315px}
```

`url` darf eine normale YouTube-URL, eine `youtu.be`-URL oder eine Embed-URL sein. YooLink wandelt sie beim Rendern in eine Embed-URL um und setzt `loading=lazy`.

### CMS Video

```markdown
::video{src=/media/yoolink/videos/demo.mp4 poster=/media/yoolink/images/poster.jpg title="CMS Video" alt="Kurze Videobeschreibung" controls preload=metadata width=100% height=420px}
```

Unterstützte Boolean-Optionen: `controls`, `autoplay`, `muted`, `loop`, `playsinline`. Wenn keine Boolean-Option gesetzt ist, nutzt YooLink standardmäßig `controls`.

Optionale Metadaten: `description`, `tags`, `duration`, `id`. Diese werden in den Builder-Code übernommen, wenn sie vorhanden sind.

### Dateien

```markdown
::file{href=/media/yoolink/files/guide.pdf title="Guide herunterladen" ext=.pdf}
```

Der sichtbare Linktext kommt aus `title`. CMS-Dateien werden mit `target="_blank"` und `rel="noopener"` gerendert.

### Code-Blöcke

````markdown
```html
<a href="/kontakt/">Kontakt aufnehmen</a>
```
````

## Copy-Paste-Beispiel ohne Medien

```markdown
## Warum ein sauberer CMS-Workflow Zeit spart

Ein guter Blogartikel beginnt nicht erst beim Schreiben. Er beginnt mit einer klaren Struktur, verständlichen Abschnitten und einem Format, das sich später ohne Reibung bearbeiten lässt. Genau dafür eignet sich Markdown im YooLink CMS.

Markdown trennt Inhalt und Darstellung. Die Redaktion kann Texte schnell einfügen, Abschnitte verschieben und später bei Bedarf im Builder weiterarbeiten. Gleichzeitig bleiben Überschriften, Listen, Links und Code-Blöcke sauber genug, um automatisch in HTML und CMS-Bausteine umgewandelt zu werden.

### Was im Alltag besser wird

- Inhalte lassen sich direkt aus KI-Tools übernehmen
- Blogartikel bleiben auch nach dem Import gut bearbeitbar
- Überschriften und Abschnitte werden konsistent aufgebaut
- Der gleiche Inhalt funktioniert im CMS UI und über die API

### Kleine Details machen den Unterschied

Nutze **fette Hervorhebungen** sparsam. Setze Links nur dort, wo sie wirklich weiterhelfen, zum Beispiel zur [Kontaktseite](/kontakt/) oder zu weiterführenden Informationen.

## Fazit

Markdown ist im YooLink CMS der schnellste Weg, um strukturierte Blogentwürfe aus externen Tools sauber zu übernehmen.
```

## Copy-Paste-Beispiel mit Bild, Galerie, Video und Datei

Ersetze die Medien-URLs bei Bedarf durch Dateien aus der CMS-Mediathek.

```markdown
## Ein Blick hinter die Kulissen des neuen Blog-Workflows

Mit dem Markdown-Modus im YooLink CMS können Blogartikel direkt aus einem externen Schreibprozess übernommen werden. Das ist besonders praktisch, wenn ein Entwurf in einem KI-Tool entsteht und danach ohne Formatierungschaos im CMS landen soll.

![Arbeitsplatz mit geöffnetem CMS und strukturiertem Blogentwurf](/media/yoolink/blogs/1/blogTitleImage.jpeg){width=100% height=auto}

### Vom Entwurf zum fertigen Artikel

Der wichtigste Schritt ist eine klare Trennung: Titel und Beschreibung werden im CMS gepflegt, der eigentliche Artikel kommt als Markdown in den Editor. Dadurch bleibt der Blog technisch sauber und redaktionell gut bearbeitbar.

- Thema und Zielgruppe festlegen
- Artikelstruktur mit Zwischenüberschriften erstellen
- Text als Markdown schreiben oder einfügen
- Bilder und Medien über das CMS auswählen
- Preview prüfen und danach veröffentlichen

### Beispiel-Galerie

:::gallery{width=100% height=420px}
![CMS Editor mit Markdown-Modus](/media/yoolink/images/cms-markdown-1.jpeg)
![Blog Preview im CMS](/media/yoolink/images/cms-preview-1.jpeg)
![Verwaltete Medien im CMS](/media/yoolink/images/cms-media-1.jpeg)
:::

### Video-Erklärung

::youtube{url=https://youtu.be/dQw4w9WgXcQ title="YooLink Blog Workflow erklärt" width=100% height=315px}

### Download

::file{href=/media/yoolink/files/blog-workflow-guide.pdf title="Workflow Guide herunterladen" ext=.pdf}

## Fazit

Der Markdown-Workflow macht YooLink flexibler, ohne den bestehenden Builder zu ersetzen. Markdown ist ideal für schnelle, saubere Textübernahme; der Builder bleibt voll synchron und kann dieselben Elemente weiterbearbeiten.
```

## Kurz-Prompt für externe KI-Tools

```text
Erstelle einen YooLink Blogartikel. Gib title, description und markdown zurück. Der Markdown-Inhalt darf kein Frontmatter enthalten und soll mit ##-Überschriften starten, weil der Titel ein eigenes CMS-Feld ist. Nutze einfache Markdown-Elemente: ##/###/####, Absätze, - Listen, **fett**, *kursiv*, `inline code`, Zitate mit "> ", Links, einzelne Bildzeilen mit ![Alt-Text](URL), optionale Größen wie {width=50% height=auto}, :::gallery-Blöcke, ::youtube{...}, ::video{...}, ::file{...} und fenced code blocks. Für Spezial-Auszeichnungen ist einfaches Inline-HTML erlaubt: <sub>, <sup>, <u>, <s>, <mark> und <span style="color: …"> bzw. background-color. Bilder und Medien müssen echte erreichbare URLs haben; für YooLink bevorzugt CMS-Medien-URLs unter /media/... . Jeder Bild-Alt-Text und jeder Videotitel muss beschreibend sein. Keine komplexen Tabellen, keine verschachtelten Listen, keine kompletten HTML-Seiten.
```
