"""Sicherungsnetz für die drei Kontaktformulare der Baugenossenschaft.

Geprüft wird die Kette vom Absenden bis ins CMS: landet die Anfrage mit der
richtigen Art in der Datenbank, geht sie per E-Mail raus, taucht sie als
Benachrichtigung mit passendem Anhänger auf und lässt sie sich dort danach
filtern und zählen.
"""

import re
from collections import Counter

import pytest
from django.core import mail
from django.test import Client
from django.urls import reverse

from yoolink.users.tests.factories import UserFactory
from yoolink.ycms.applications.notifications.models import Notification
from yoolink.ycms.models import Message, WebsiteSettings

pytestmark = pytest.mark.django_db


ALLGEMEIN = {
    "formular": "allgemein",
    "anrede": "Frau",
    "name": "Anna Beispiel",
    "email": "anna@example.org",
    "telefon": "09931 12345",
    "betreff": "Anliegen als Mieter",
    "nachricht": "Die Gegensprechanlage im Treppenhaus funktioniert seit gestern nicht mehr.",
    "datenschutz": "on",
    "website": "",
}

MITGLIEDSCHAFT = {
    "formular": "mitgliedschaft",
    "anrede": "Herr",
    "name": "Bernd Muster",
    "email": "bernd@example.org",
    "geburtsdatum": "1985-04-17",
    "strasse": "Bahnhofstr. 3",
    "plz_ort": "94447 Plattling",
    "haushalt": "2 Personen",
    "wohnungsgroesse": "3 Zimmer",
    "einzug": "2026-10-01",
    "nachricht": "Wir moechten Mitglied werden und suchen eine Wohnung fuer zwei Personen.",
    "datenschutz": "on",
    "website": "",
}

REPARATUR = {
    "formular": "reparatur",
    "anrede": "Frau",
    "name": "Clara Mieterin",
    "email": "clara@example.org",
    "telefon": "0170 1234567",
    "mitgliedsnummer": "4711",
    "objekt": "Schillerstr. 6b, 94447 Plattling",
    "wohnungslage": "2. Stock links",
    "schadensart": "Heizung / Warmwasser",
    "dringlichkeit": "Dringend",
    "erreichbarkeit": "werktags ab 16 Uhr",
    "nachricht": "Die Heizung im Wohnzimmer wird seit drei Tagen nicht mehr warm.",
    "datenschutz": "on",
    "website": "",
}


def _details(message):
    return {row["label"]: row["value"] for row in message.detail_rows}


def test_kontakt_page_offers_all_three_forms(client):
    response = client.get(reverse("kontakt"))

    assert response.status_code == 200
    body = response.content.decode()
    for key in ("allgemein", "mitgliedschaft", "reparatur"):
        assert f'data-bgp-tab="{key}"' in body
        assert f'data-bgp-form="{key}"' in body
        assert f'<input type="hidden" name="formular" value="{key}" />' in body

    keys = [entry["key"] for entry in response.context["contact_forms"]]
    assert keys == ["allgemein", "mitgliedschaft", "reparatur"]
    assert response.context["active_form_key"] == "allgemein"


def test_the_three_forms_do_not_share_field_ids(client):
    """Alle drei stehen auf derselben Seite - doppelte ``id`` würden die
    Beschriftungen auf das jeweils erste Formular zeigen lassen."""
    body = client.get(reverse("kontakt")).content.decode()

    ids = re.findall(r'<(?:input|select|textarea)[^>]*\sid="([^"]+)"', body)
    duplicates = [value for value, count in Counter(ids).items() if count > 1]
    assert duplicates == []

    for prefix in ("id_general_", "id_membership_", "id_repair_"):
        assert f'{prefix}name"' in body
        assert f'for="{prefix}name"' in body


@pytest.mark.parametrize("key", ["allgemein", "mitgliedschaft", "reparatur"])
def test_query_parameter_preselects_a_form(client, key):
    response = client.get(reverse("kontakt"), {"formular": key})

    assert response.context["active_form_key"] == key
    active = [entry["key"] for entry in response.context["contact_forms"] if entry["is_active"]]
    assert active == [key]


def test_unknown_form_key_falls_back_to_the_default(client):
    response = client.get(reverse("kontakt"), {"formular": "gibt-es-nicht"})

    assert response.context["active_form_key"] == "allgemein"


@pytest.mark.parametrize(
    "payload,category,expected_title",
    [
        (ALLGEMEIN, Message.Category.GENERAL, "Anliegen als Mieter"),
        (MITGLIEDSCHAFT, Message.Category.MEMBERSHIP, "Bewerbung um eine Mitgliedschaft"),
        (REPARATUR, Message.Category.REPAIR, "Reparatur: Heizung / Warmwasser"),
    ],
)
def test_submitting_a_form_stores_the_request_with_its_category(client, payload, category, expected_title):
    response = client.post(reverse("kontakt"), payload)

    # Post/Redirect/Get: ein Neuladen darf die Anfrage nicht wiederholen.
    assert response.status_code == 302
    assert f"gesendet={payload['formular']}" in response["Location"]

    message = Message.objects.get()
    assert message.category == category
    assert message.title == expected_title
    assert message.email == payload["email"]
    assert message.phone == payload.get("telefon", "")
    assert payload["anrede"] in message.name


def test_membership_form_keeps_its_extra_answers(client):
    client.post(reverse("kontakt"), MITGLIEDSCHAFT)

    details = _details(Message.objects.get())
    assert details["Geburtsdatum"] == "17.04.1985"
    assert details["Anschrift"] == "Bahnhofstr. 3 94447 Plattling"
    assert details["Personen im Haushalt"] == "2 Personen"
    assert details["Gewünschte Wohnungsgröße"] == "3 Zimmer"
    assert details["Gewünschter Einzug"] == "01.10.2026"
    assert details["Bereits Mitglied"] == "Nein"


def test_repair_form_keeps_its_extra_answers(client):
    client.post(reverse("kontakt"), REPARATUR)

    details = _details(Message.objects.get())
    assert details["Mitgliedsnummer"] == "4711"
    assert details["Objekt / Anschrift"] == "Schillerstr. 6b, 94447 Plattling"
    assert details["Lage der Wohnung"] == "2. Stock links"
    assert details["Art des Schadens"] == "Heizung / Warmwasser"
    assert details["Dringlichkeit"] == "Dringend"
    assert details["Erreichbarkeit"] == "werktags ab 16 Uhr"


@pytest.mark.parametrize(
    "payload,subject_tag,notification_title",
    [
        (ALLGEMEIN, "[Allgemein]", "Neue Kontaktanfrage"),
        (MITGLIEDSCHAFT, "[Mitgliedschaft]", "Neue Bewerbung um eine Mitgliedschaft"),
        (REPARATUR, "[Reparatur]", "Neue Reparaturanfrage"),
    ],
)
def test_request_is_mailed_and_shows_up_as_notification(client, payload, subject_tag, notification_title):
    WebsiteSettings.objects.create(company_name="Baugenossenschaft Plattling eG", contact_email="buero@example.org")
    mail.outbox = []

    client.post(reverse("kontakt"), payload)

    message = Message.objects.get()
    internal, confirmation = mail.outbox
    assert internal.to == ["buero@example.org"]
    assert internal.subject.startswith(subject_tag)
    # Eine Antwort im Postfach soll direkt beim Absender landen.
    assert internal.reply_to == [payload["email"]]
    assert payload["nachricht"] in internal.body
    assert confirmation.to == [payload["email"]]

    notification = Notification.objects.get(message=message)
    assert notification.title == notification_title
    assert notification.category == message.category
    assert notification.is_contact_request is True


def test_mail_failure_does_not_lose_the_request(client, settings, caplog):
    """Ein kaputter Mailversand darf die Anfrage nicht verschlucken."""
    settings.EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    settings.EMAIL_HOST = "127.0.0.1"
    settings.EMAIL_PORT = 1  # Verbindung schlägt sofort fehl.
    WebsiteSettings.objects.create(contact_email="buero@example.org")

    response = client.post(reverse("kontakt"), ALLGEMEIN)

    assert response.status_code == 302
    assert Message.objects.count() == 1
    assert Notification.objects.count() == 1


def test_invalid_submission_reopens_the_same_form_with_errors(client):
    mail.outbox = []

    response = client.post(
        reverse("kontakt"),
        {"formular": "reparatur", "name": "", "email": "keine-mail", "nachricht": "kurz"},
    )

    assert response.status_code == 200
    assert Message.objects.count() == 0
    assert mail.outbox == []
    assert response.context["active_form_key"] == "reparatur"

    entries = {entry["key"]: entry for entry in response.context["contact_forms"]}
    assert entries["reparatur"]["form"].errors
    # Die beiden anderen Reiter bleiben leer - dort soll kein fremder Fehler stehen.
    assert not entries["allgemein"]["form"].is_bound
    assert not entries["mitgliedschaft"]["form"].is_bound


@pytest.mark.parametrize("key", ["allgemein", "mitgliedschaft", "reparatur"])
def test_each_form_carries_a_working_csrf_token(key):
    """Jedes der drei Formulare muss im echten Browser absendbar sein.

    Die Formulare stecken in einem ``{% include ... only %}``; ohne ausdrücklich
    durchgereichtes ``csrf_token`` rendert das Feld leer und jedes Absenden
    scheitert mit 403 - was der Test-Client mit abgeschaltetem CSRF-Schutz nicht
    bemerkt. Deshalb hier ein Client, der prüft.
    """
    strict = Client(enforce_csrf_checks=True)

    page = strict.get(reverse("kontakt")).content.decode()
    tokens = re.findall(r'name="csrfmiddlewaretoken" value="([^"]+)"', page)
    assert len(tokens) == 3, "jedes der drei Formulare braucht ein eigenes CSRF-Feld"

    payload = {"allgemein": ALLGEMEIN, "mitgliedschaft": MITGLIEDSCHAFT, "reparatur": REPARATUR}[key]
    response = strict.post(reverse("kontakt"), {**payload, "csrfmiddlewaretoken": tokens[0]})

    assert response.status_code == 302
    assert Message.objects.count() == 1


def test_honeypot_field_blocks_automated_submissions(client):
    response = client.post(reverse("kontakt"), {**ALLGEMEIN, "website": "http://spam.example"})

    assert response.status_code == 200
    assert Message.objects.count() == 0


def test_confirmation_is_shown_after_the_redirect(client):
    response = client.post(reverse("kontakt"), MITGLIEDSCHAFT, follow=True)

    assert response.context["success"] is True
    assert response.context["success_form_label"] == "Mitglied werden"
    assert response.context["success_email"] == MITGLIEDSCHAFT["email"]

    # Beim erneuten Aufruf ohne Absenden darf keine Bestätigung mehr erscheinen.
    again = client.get(reverse("kontakt"))
    assert again.context["success"] is False


def test_cms_overview_counts_and_filters_by_category(client):
    for payload in (ALLGEMEIN, MITGLIEDSCHAFT, MITGLIEDSCHAFT, REPARATUR):
        client.post(reverse("kontakt"), payload)

    staff = UserFactory(is_staff=True, is_superuser=True)
    client.force_login(staff)

    overview = client.get(reverse("cms:notifications-list"))
    assert overview.status_code == 200
    counts = {row["value"]: row["count"] for row in overview.context["category_summary"]}
    assert counts["general"] == 1
    assert counts["membership"] == 2
    assert counts["repair"] == 1

    filtered = client.get(reverse("cms:notifications-list"), {"category": "membership"})
    assert filtered.context["filter_category"] == "membership"
    assert [n.category for n in filtered.context["notifications"]] == ["membership", "membership"]
    # Die Zahlen bleiben die des gesamten Posteingangs, sonst sieht man nicht
    # mehr, was in den anderen Arten liegt.
    assert {row["value"]: row["count"] for row in filtered.context["category_summary"]} == counts

    unknown = client.get(reverse("cms:notifications-list"), {"category": "quatsch"})
    assert unknown.context["filter_category"] == "all"
    assert unknown.context["filtered_count"] == 4


def test_cms_detail_shows_the_category_and_the_extra_answers(client):
    client.post(reverse("kontakt"), REPARATUR)

    staff = UserFactory(is_staff=True, is_superuser=True)
    client.force_login(staff)

    notification = Notification.objects.get()
    body = client.get(reverse("cms:notification-detail", args=[notification.pk])).content.decode()

    assert "Reparaturservice" in body
    assert "Art des Schadens" in body
    assert "Heizung / Warmwasser" in body
    assert "0170 1234567" in body


def test_cms_editor_page_lets_the_customer_edit_all_three_forms(client):
    client.force_login(UserFactory(is_staff=True, is_superuser=True))

    response = client.get(reverse("cms:site_kontakt"))

    assert response.status_code == 200
    body = response.content.decode()
    for key in ("allgemein", "mitgliedschaft", "reparatur"):
        assert f'key="main_bgp_contact_form_{key}"' in body
    assert 'key="main_bgp_contact_forms_help"' in body


def test_category_counts_survive_a_deleted_message(client):
    """Die Art hängt an der Benachrichtigung, nicht nur an der Anfrage."""
    client.post(reverse("kontakt"), REPARATUR)
    Message.objects.all().delete()

    notification = Notification.objects.get()
    assert notification.message_id is None
    assert notification.category == Message.Category.REPAIR
    assert notification.category_meta["short"] == "Reparatur"


BODY = re.compile(r"<body\b.*?</body>", re.S | re.I)


def _visible(html):
    """Seiteninhalt ohne <style>/<script>, dort sind Kommentare normal."""
    body = BODY.search(html)
    text = body.group(0) if body else html
    text = re.sub(r"<(style|script)\b.*?</\1>", "", text, flags=re.S | re.I)
    return text


def test_no_template_comment_text_leaks_into_the_cms_pages(client):
    message = Message.objects.create(
        name="Testerin", email="t@example.org", title="Reparatur: Elektro",
        message="Steckdose kaputt", category=Message.Category.REPAIR,
        phone="0170", details=[{"label": "Objekt", "value": "Schillerstr. 6b"}],
    )
    client.force_login(UserFactory(is_staff=True, is_superuser=True))
    notification = message.notifications.get()

    pages = [
        reverse("cms:notifications-list"),
        reverse("cms:notifications-spam-list"),
        reverse("cms:site_kontakt"),
        reverse("cms:notification-detail", args=[notification.pk]),
    ]
    needles = ["Symbol und Farbe", "Zusatzangaben unterscheiden sich",
               "Anzahl je Art", "Wegweiser in der rechten Spalte",
               "Farben stehen als ganze Klassennamen", "{#", "endcomment"]

    for url in pages:
        response = client.get(url)
        assert response.status_code == 200, url
        text = _visible(response.content.decode())
        for needle in needles:
            assert needle not in text, f"{url}: '{needle}' steht sichtbar in der Seite"


def test_no_template_comment_text_leaks_into_the_contact_page(client):
    text = _visible(client.get(reverse("kontakt")).content.decode())

    for needle in ["haelt fremde Variablen", "Sagt der Seitenlogik", "Spam-Falle",
                   "Beschriftung, Pflichtstern", "{#", "endcomment"]:
        assert needle not in text, f"'{needle}' steht sichtbar in der Seite"
