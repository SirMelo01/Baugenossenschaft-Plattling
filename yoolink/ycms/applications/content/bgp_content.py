"""Gemeinsame Definition der CMS-Textbausteine der Baugenossenschaft-Plattling-Seiten.

Die oeffentliche Seite (``yoolink/views.py``) und der CMS-Editor
(``ycms/applications/content/views.py``) haben Key-Liste und Standardtexte frueher
getrennt gepflegt und sind dadurch auseinandergelaufen. Beide lesen jetzt diese
Datei, damit ein Textbaustein nicht auf einer Seite anders aussehen kann als auf
der anderen.

Ein ``TextContent``-Datensatz hat vier Felder (``header`` / ``title`` /
``description`` / ``buttonText``). Reicht das fuer einen Abschnitt nicht, bekommt
er einen eigenen Key (z.B. ``..._date`` oder ``..._text2``).

Kontextname im Template ist ``bgp_<suffix>``, der DB-Name ``main_bgp_<suffix>``.
Im Template steht dann immer der *effektive* Text: der im CMS gepflegte Wert,
sonst der Standardtext von hier. Ein ``|default:``-Fallback im Template ist damit
weder noetig noch erwuenscht.
"""

import re
from urllib.parse import urlencode

TEXT_FIELDS = ("header", "title", "description", "buttonText")

# Standardtexte je Baustein. Nur gefuellte Felder auflisten; alles andere ist "".
BGP_DEFAULTS = {
    # ─────────── Startseite: Hero ───────────
    "hero": {
        "title": "Gemeinsam bauen.\nSicher wohnen.",
        "header": "Seit 1921 in Plattling.",
        "description": (
            "Als Genossenschaft bieten wir unseren Mitgliedern bezahlbaren, sicheren "
            "Wohnraum in Plattling. Werden Sie Teil einer starken Gemeinschaft - mit "
            "Mitspracherecht, fairen Mieten und einer Dividende von aktuell 3 % auf "
            "Ihre Geschäftsanteile."
        ),
        "buttonText": "Wohnungsangebote",
    },
    "hero_secondary": {"buttonText": "Kontakt aufnehmen"},
    "hero_bild": {
        "title": "Büro- und Geschäftsgebäude der Baugenossenschaft Plattling eG",
        "description": "Unser Büro- und Geschäftsgebäude in der Schillerstraße 6b",
    },
    "hero_badge_1": {"title": "100+", "description": "Jahre Erfahrung"},
    "hero_badge_2": {"title": "3 %", "description": "Dividende 2025"},

    # ─────────── Startseite: Faktenleiste ───────────
    "fact_1": {"title": "1921", "description": "gegründet"},
    "fact_2": {"title": "3 % Dividende", "description": "stabil seit Jahren"},
    "fact_3": {"title": "Mitglieder", "description": "statt nur Mieter"},
    "fact_4": {"title": "Mo / Mi / Fr", "description": "8:00 - 12:00 Uhr"},

    # ─────────── Startseite: Unsere Genossenschaft ───────────
    "genossenschaft": {
        "header": "Unsere Genossenschaft",
        "title": "Mehr als nur ein Vermieter",
        "description": (
            "Die Baugenossenschaft Plattling eG steht seit über 100 Jahren für sicheres, "
            "bezahlbares Wohnen in der Region. Anders als bei einem klassischen Vermieter "
            "sind unsere Mieter zugleich Mitglieder und Miteigentümer der Genossenschaft."
        ),
    },
    "genossenschaft_text2": {
        "description": (
            "Das bedeutet für Sie: faire Mieten, lebenslanges Wohnrecht und ein echtes "
            "Mitspracherecht. Unsere Mitglieder wählen den Aufsichtsrat und gestalten die "
            "Zukunft der Genossenschaft aktiv mit - gelebte Demokratie im Wohnungswesen, "
            "jedes Jahr aufs Neue bei unserer Mitgliederversammlung."
        ),
    },
    "benefit_1": {"title": "Faire, stabile Mieten"},
    "benefit_2": {"title": "Lebenslanges Wohnrecht"},
    "benefit_3": {"title": "Mitspracherecht als Mitglied"},
    "benefit_4": {"title": "3 % Dividende auf Anteile"},
    "feature_about": {
        "title": "Wir über uns",
        "description": (
            "Gepflegte Wohngebäude an zentralen und ruhigen Lagen in Plattling - mit "
            "Weitblick verwaltet und regelmäßig modernisiert."
        ),
    },
    "feature_organe": {
        "title": "Organe",
        "description": (
            "Vorstand und Aufsichtsrat arbeiten ehrenamtlich und transparent - gewählt "
            "von den Mitgliedern der Genossenschaft."
        ),
    },
    "feature_historie": {
        "header": "seit 1921",
        "title": "Historie seit 1921",
        "description": (
            "Über ein Jahrhundert Genossenschaftsgeschichte in Plattling: vom Wiederaufbau "
            "bis zur laufenden Modernisierung unserer Objekte."
        ),
    },

    # ─────────── Startseite: Vermietung ───────────
    "vermietung": {
        "header": "Vermietung",
        "title": "Ihr neues Zuhause in Plattling",
        "description": (
            "Wir vermieten gepflegte Wohnungen an unsere Mitglieder - für Singles, Paare "
            "und Familien."
        ),
        "buttonText": "Verfügbare Objekte erfragen",
    },
    "rental_angebote": {
        "title": "Mietangebote",
        "description": (
            "Aktuelle freie Wohnungen auf einen Blick - fragen Sie gerne auch telefonisch "
            "nach kommenden Angeboten."
        ),
    },
    "rental_objekte": {
        "title": "Unsere Objekte",
        "description": (
            "Unsere Wohnanlagen in Plattling - zentral gelegen, gepflegt und laufend "
            "modernisiert."
        ),
    },
    "rental_bewerbung": {
        "title": "Bewerbungsformular",
        "description": (
            "Interesse an einer Wohnung? Mit dem Bewerbungsformular nehmen wir Sie in "
            "unsere Interessentenliste auf."
        ),
    },
    "rental_infos": {
        "title": "Wichtige Mieterinfos",
        "description": (
            "Alles Wissenswerte für unsere Mieter - von Nebenkosten bis zu aktuellen "
            "Hinweisen rund um Ihre Wohnung."
        ),
    },

    # ─────────── Startseite: Aktuelles-Teaser ───────────
    "home_aktuelles": {
        "header": "Aktuelles",
        "title": "Neuigkeiten aus der Genossenschaft",
        "buttonText": "Weitere Neuigkeiten",
    },
    # Die Karten selbst kommen aus dem Blog-Modul (siehe home_news_posts()); hier
    # stehen nur die Beschriftungen, die auf jeder Karte gleich sind.
    "home_news_card": {"header": "Aktuelles", "buttonText": "Mehr erfahren"},
    "home_news_empty": {
        "title": "Zurzeit nichts Aktuelles",
        "description": (
            "Sobald es Neuigkeiten aus der Genossenschaft gibt, finden Sie sie hier."
        ),
    },

    # ─────────── Startseite: Kontakt-Teaser ───────────
    "kontakt_teaser": {
        "header": "Kontakt",
        "title": "So erreichen Sie uns",
        "description": (
            "Wir sind persönlich für Sie da - rufen Sie uns an oder besuchen Sie uns in "
            "der Schillerstraße."
        ),
    },
    # Die vier Infokarten: Inhalt kommt aus den Website-Daten (contact_details) bzw.
    # dem Modul "Oeffnungszeiten". Hier stehen bewusst nur die Ueberschriften -
    # Anschrift, Telefon und E-Mail duerfen kein zweites Mal im Code liegen, sonst
    # widerspricht der Standardtext irgendwann den gepflegten Daten. ``description``
    # bleibt leer und dient nur als Rueckfallebene, falls das Feld im Profil fehlt.
    "contact_card_1": {"title": "Anschrift"},
    "contact_card_2": {"title": "Telefon & Fax"},
    "contact_card_3": {"title": "E-Mail"},
    "contact_card_4": {
        "title": "Öffnungszeiten",
        "buttonText": "An Brückentagen ist unser Büro geschlossen.",
    },
    # Der zweite Button zeigt die Telefonnummer aus den Website-Daten (contact_details).
    "kontakt_cta": {
        "description": "Sie haben Fragen oder möchten Mitglied werden?",
        "buttonText": "Zum Kontaktformular",
    },

    # ─────────── Aktuelles-Seite ───────────
    "news_hero": {
        "header": "Aktuelles",
        "title": "Neuigkeiten aus der Genossenschaft",
        "description": (
            "Meldungen aus dem Genossenschaftsleben: Mitgliederversammlungen, Modernisierungen "
            "an unseren Objekten, Stellenangebote und alles, was unsere Mitglieder und Mieter betrifft."
        ),
    },
    # Die Meldungen selbst kommen aus dem Blog-Modul; hier stehen nur die
    # Beschriftungen, die auf jeder Karte gleich sind, und die Leertexte.
    "news_card": {
        "header": "Aktuelles",
        "buttonText": "Mehr erfahren",
        "title": "Top-Meldung",
    },
    "news_overview": {
        "title": "Alle Meldungen",
        "description": "Zurzeit gibt es keine weiteren Meldungen.",
    },
    "news_empty": {
        "title": "Zurzeit nichts Aktuelles",
        "description": (
            "Sobald es Neuigkeiten aus der Genossenschaft gibt, finden Sie sie hier."
        ),
    },
    # ─────────── Aktuelles: Detailseite einer Meldung ───────────
    "news_detail": {
        "header": "Aktuelles",
        "buttonText": "Zurück zur Übersicht",
        "title": "Weitere Meldungen",
    },
    "news_cta": {
        "title": "Keine Neuigkeit verpassen",
        "description": (
            "Wichtige Meldungen schicken wir unseren Mitgliedern auch per Post. Fragen zu einer "
            "Meldung? Melden Sie sich einfach bei uns."
        ),
        "buttonText": "Kontakt aufnehmen",
    },

    # ─────────── Kontaktseite ───────────
    "contact_hero": {
        "header": "Kontakt",
        "title": "Wir sind für Sie da",
        "description": (
            "Ob Frage zur Mitgliedschaft, Interesse an einer Wohnung oder ein Anliegen rund um "
            "Ihre Mietwohnung: Schreiben Sie uns über das Formular oder rufen Sie einfach an."
        ),
    },
    # Wie bei den Kontaktkarten der Startseite stehen hier nur die Ueberschriften.
    # Telefonnummer, E-Mail, Anschrift und Zeiten kommen aus den Website-Daten
    # (contact_details) bzw. dem Modul "Oeffnungszeiten"; ``description`` bleibt
    # leer und dient nur als Rueckfallebene, falls dort nichts gepflegt ist.
    "contact_tile_1": {"title": "Telefon"},
    "contact_tile_2": {"title": "E-Mail"},
    "contact_tile_3": {"title": "Bürozeiten"},
    "contact_form": {"title": "Schreiben Sie uns"},
    "contact_address": {"title": "Anschrift"},
    "contact_map": {
        "description": "Parkplätze direkt am Haus",
        "buttonText": "Route",
    },
    # Die Tabelle darunter kommt aus dem Modul "Oeffnungszeiten"; ``description`` ist
    # die Rueckfallebene, falls dort kein Tag gepflegt ist.
    "contact_hours": {
        "title": "Öffnungszeiten",
        "buttonText": (
            "An Brückentagen ist unser Büro geschlossen. Termine außerhalb der "
            "Bürozeiten vereinbaren wir gerne telefonisch."
        ),
    },
    "contact_emergency": {
        "title": "Notfall außerhalb der Bürozeiten?",
        "description": (
            "Bei akuten Schäden - etwa Wasserrohrbruch oder Heizungsausfall - erreichen Sie "
            "unseren Bereitschaftsdienst rund um die Uhr unter der bekannten Rufnummer."
        ),
        "buttonText": "Jetzt anrufen",
    },
    "contact_success": {
        "title": "Vielen Dank für Ihre Nachricht!",
        "description": (
            "Wir haben Ihre Anfrage erhalten und melden uns in der Regel innerhalb von zwei "
            "Werktagen bei Ihnen zurück."
        ),
    },
}

BGP_TEXT_KEYS = list(BGP_DEFAULTS)

# Bild-Slots: Kontextname -> ``place`` in der Mediathek.
BGP_IMAGE_KEYS = {
    "bgp_hero_image": "main_bgp_hero",
}


# Anzahl der Blogbeitraege im Aktuelles-Teaser der Startseite.
HOME_NEWS_COUNT = 3


def home_news_posts(limit=HOME_NEWS_COUNT):
    """Die neuesten Blogbeitraege fuer den Aktuelles-Teaser der Startseite.

    Der Teaser hat keine eigenen Texte - er zeigt dieselben Beitraege wie die
    Blog-Uebersicht und wird ausschliesslich unter "Blogs" gepflegt.

    Auswahl wie in ``yoolink/blog/views.py``: nur aktive Originale, neueste zuerst,
    und - falls vorhanden - die Uebersetzung in der Seitensprache.
    """
    from django.conf import settings as django_settings

    from yoolink.ycms.models import Blog

    originals = (
        Blog.objects.filter(original__isnull=True, active=True)
        .order_by("-date")
        .prefetch_related("translations")[:limit]
    )
    posts = []
    for blog in originals:
        variant = blog.translations.filter(
            language=django_settings.LANGUAGE_CODE, active=True
        ).first()
        posts.append(variant or blog)
    return posts


# Wochentage in Anzeigereihenfolge: DB-Wert von ``OpeningHours.day`` -> Kurzform.
_WEEKDAY_SHORT = (
    ("MON", "Mo"),
    ("TUE", "Di"),
    ("WED", "Mi"),
    ("THU", "Do"),
    ("FRI", "Fr"),
    ("SAT", "Sa"),
    ("SUN", "So"),
)

# Ausgeschriebene Namen fuer die Oeffnungszeiten-Tabelle der Kontaktseite.
_WEEKDAY_LONG = dict(
    zip(
        (day for day, _ in _WEEKDAY_SHORT),
        (
            "Montag",
            "Dienstag",
            "Mittwoch",
            "Donnerstag",
            "Freitag",
            "Samstag",
            "Sonntag",
        ),
    )
)


def _format_time(value, pad=False):
    """``08:00`` -> ``"8:00"`` - ohne fuehrende Null, wie im Seitenentwurf.

    ``pad=True`` liefert ``"08:00"`` fuer die Tabelle auf der Kontaktseite, in der
    die Uhrzeiten untereinander stehen und buendig bleiben sollen.
    """
    return f"{value.hour:02d}:{value.minute:02d}" if pad else f"{value.hour}:{value.minute:02d}"


def _format_days(shorts):
    """``["Mo","Mi","Fr"]`` -> ``"Mo / Mi / Fr"``, ``["Mo".."Fr"]`` -> ``"Mo - Fr"``.

    Aufeinanderfolgende Tage werden erst ab drei Stueck zu einem Bereich
    zusammengefasst; bei zweien ist ``Mo / Di`` kuerzer als ``Mo - Di``.
    """
    order = [short for _, short in _WEEKDAY_SHORT]
    runs = []
    for short in shorts:
        if runs and order.index(short) == order.index(runs[-1][-1]) + 1:
            runs[-1].append(short)
        else:
            runs.append([short])
    return " / ".join(
        f"{run[0]} - {run[-1]}" if len(run) >= 3 else " / ".join(run) for run in runs
    )


def opening_hours_groups():
    """Die Oeffnungszeiten aus dem CMS-Modul, nach gleichen Zeiten gruppiert.

    Ergebnis z.B. ``[{"days": "Mo / Mi / Fr", "times": "8:00 - 12:00 Uhr"}]``;
    leer, wenn kein Tag als geoeffnet gepflegt ist. Mehrere Zeitraeume an einem
    Tag (Mittagspause) stehen in derselben ``times``-Zeile.
    """
    from yoolink.ycms.models import OpeningHours, WebsiteSettings

    rows = {
        row.day: row
        for row in OpeningHours.objects.filter(
            website=WebsiteSettings.get_solo(), is_open=True
        )
    }

    groups = []  # [(zeiten, [kurzform, ...]), ...] in Wochentagsreihenfolge
    for day, short in _WEEKDAY_SHORT:
        row = rows.get(day)
        if row is None:
            continue
        periods = tuple(
            f"{_format_time(start)} - {_format_time(end)}"
            for start, end in row.calculate_opening_periods()
        )
        if not periods:
            continue
        for times, shorts in groups:
            if times == periods:
                shorts.append(short)
                break
        else:
            groups.append((periods, [short]))

    return [
        {"days": _format_days(shorts), "times": f"{' / '.join(times)} Uhr"}
        for times, shorts in groups
    ]


def opening_hours_fact(groups=None):
    """Die Oeffnungszeiten als zweizeilige Faktenkachel der Startseite.

    Ergebnis z.B. ``{"title": "Mo / Mi / Fr", "description": "8:00 - 12:00 Uhr"}``.

    ``None``, wenn kein Tag als geoeffnet gepflegt ist - dann bleibt der im CMS
    hinterlegte bzw. der Standardtext der Kachel stehen.

    In die Kachel passen nur zwei Zeilen: haben nicht alle geoeffneten Tage
    dieselben Zeiten, zeigt sie die erste Gruppe. Die vollstaendige Aufstellung
    steht in der Kontaktkachel und auf der Kontaktseite.
    """
    groups = opening_hours_groups() if groups is None else groups
    if not groups:
        return None
    return {"title": groups[0]["days"], "description": groups[0]["times"]}


def opening_hours_summary(groups=None):
    """Die Oeffnungszeiten einzeilig, z.B. ``"Mo / Mi / Fr · 8:00 - 12:00 Uhr"``.

    Fuer die schmale Kachel im Kopfbereich der Kontaktseite. ``""``, wenn kein Tag
    als geoeffnet gepflegt ist - dann bleibt der Text der Kachel stehen. Haben nicht
    alle Tage dieselben Zeiten, zeigt die Kachel die erste Gruppe; die vollstaendige
    Aufstellung steht in der Oeffnungszeiten-Karte weiter unten.
    """
    fact = opening_hours_fact(groups)
    if not fact:
        return ""
    return f"{fact['title']} · {fact['description']}"


def opening_hours_table():
    """Die Oeffnungszeiten als Tabelle fuer die Kontaktseite.

    Ergebnis z.B.::

        {"rows": [{"day": "Montag", "times": "08:00 - 12:00"}, ...],
         "closed": "Di / Do / Sa / So"}

    ``rows`` listet jeden geoeffneten Tag einzeln mit ausgeschriebenem Namen, damit
    die Karte lesbar bleibt; alle uebrigen Tage stehen zusammengefasst in ``closed``.
    Ohne gepflegte Zeiten ist ``rows`` leer und die Karte blendet die Tabelle aus.
    """
    from yoolink.ycms.models import OpeningHours, WebsiteSettings

    rows_by_day = {
        row.day: row
        for row in OpeningHours.objects.filter(
            website=WebsiteSettings.get_solo(), is_open=True
        )
    }

    rows = []
    closed = []
    for day, short in _WEEKDAY_SHORT:
        row = rows_by_day.get(day)
        periods = row.calculate_opening_periods() if row is not None else []
        times = " / ".join(
            f"{_format_time(start, pad=True)} - {_format_time(end, pad=True)}"
            for start, end in periods
        )
        if times:
            rows.append({"day": _WEEKDAY_LONG[day], "times": times})
        else:
            closed.append(short)

    return {"rows": rows, "closed": _format_days(closed) if rows and closed else ""}


def _tel_href(number):
    """``"09931 890073-0"`` -> ``"tel:099318900730"``; leer, wenn keine Ziffern."""
    raw = (number or "").strip()
    digits = re.sub(r"\D", "", raw)
    if not digits:
        return ""
    return f"tel:{'+' if raw.startswith('+') else ''}{digits}"


def contact_details():
    """Kontaktdaten aus dem Unternehmensprofil (CMS-Einstellungen).

    Damit stehen Anschrift, Telefon und E-Mail nur an einer Stelle und koennen auf
    der Seite nicht von den Einstellungen abweichen. Nicht gepflegte Felder kommen
    als leerer String zurueck; die Templates blenden die Zeile dann aus.
    """
    from yoolink.ycms.models import WebsiteSettings

    owner = WebsiteSettings.get_solo()
    company_name = (owner.company_name or "").strip()
    # "Schillerstr. 6b, 94447 Plattling" -> zwei Zeilen auf der Karte.
    address_lines = [
        part.strip() for part in (owner.address or "").split(",") if part.strip()
    ]
    address_inline = ", ".join(address_lines)
    # Routenplaner-Link der Kontaktseite. Firmenname davor, damit die Karte auch bei
    # knapper Anschrift den richtigen Punkt trifft; ohne Anschrift bleibt er leer und
    # die Karte zeigt keinen Button.
    maps_url = ""
    if address_inline:
        destination = f"{company_name}, {address_inline}" if company_name else address_inline
        maps_url = "https://www.google.com/maps/dir/?" + urlencode(
            {"api": "1", "destination": destination}
        )
    return {
        "company_name": company_name,
        "address_lines": address_lines,
        "address_inline": address_inline,
        "maps_url": maps_url,
        "tel": (owner.tel_number or "").strip(),
        "tel_href": _tel_href(owner.tel_number),
        "fax": (owner.fax_number or "").strip(),
        "email": (owner.contact_email or "").strip(),
    }


def _merged(text_obj, defaults):
    """Im CMS gepflegter Wert, sonst Standardtext - pro Feld."""
    values = {field: defaults.get(field, "") for field in TEXT_FIELDS}
    if text_obj is not None:
        for field in TEXT_FIELDS:
            saved = (getattr(text_obj, field, "") or "").strip()
            if saved:
                values[field] = saved
    return values


def bgp_content_context():
    """Alle Textbausteine und Bilder der Baugenossenschaft-Seiten (effektive Werte)."""
    # Lokal importieren, damit dieses Modul ohne geladene App-Registry importierbar bleibt.
    from yoolink.ycms.models import fileentry

    from .models import TextContent

    saved = {
        obj.name: obj
        for obj in TextContent.objects.filter(
            name__in=[f"main_bgp_{key}" for key in BGP_TEXT_KEYS]
        )
    }
    context = {
        f"bgp_{key}": _merged(saved.get(f"main_bgp_{key}"), defaults)
        for key, defaults in BGP_DEFAULTS.items()
    }

    # Die vierte Faktenkachel kommt aus dem CMS-Modul "Oeffnungszeiten", damit die
    # Zeiten nicht an zwei Stellen gepflegt werden muessen. Ist dort nichts
    # hinterlegt, bleibt der Text der Kachel stehen.
    groups = opening_hours_groups()
    fact = opening_hours_fact(groups)
    context["bgp_opening_hours_groups"] = groups
    context["bgp_opening_hours_auto"] = fact is not None
    if fact:
        context["bgp_fact_4"] = {**context["bgp_fact_4"], **fact}

    # Kontaktseite: einzeilige Kachel im Kopfbereich und Tabelle in der Karte.
    context["bgp_opening_hours_summary"] = opening_hours_summary(groups)
    context["bgp_opening_hours_table"] = opening_hours_table()

    # Aktuelles-Teaser der Startseite: Karten kommen aus dem Blog-Modul.
    context["bgp_home_news_posts"] = home_news_posts()

    # Kontakt-Teaser: Anschrift/Telefon/E-Mail aus dem Unternehmensprofil.
    context["bgp_contact"] = contact_details()

    images = {img.place: img for img in fileentry.objects.filter(place__in=BGP_IMAGE_KEYS.values())}
    context.update({name: images.get(place) for name, place in BGP_IMAGE_KEYS.items()})
    return context
