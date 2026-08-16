from datetime import time

import pytest
from django.urls import reverse

from yoolink.users.tests.factories import UserFactory
from yoolink.ycms.applications.content.bgp_content import opening_hours_fact
from yoolink.ycms.applications.content.models import TextContent
from yoolink.ycms.models import (
    Blog,
    FAQ,
    OpeningHours,
    PricingCard,
    TeamMember,
    WebsiteSettings,
)

pytestmark = pytest.mark.django_db


def test_home_page_renders_cms_managed_content(client):
    TextContent.objects.create(
        name="main_hero",
        header="Webdesign",
        title="YooLink",
        description="CMS gesteuerte Inhalte",
        buttonText="Kontakt",
    )
    TextContent.objects.create(name="footer", description="Footer Text")
    FAQ.objects.create(question="Was ist YooLink?", answer="Ein CMS.")
    TeamMember.objects.create(full_name="Jane Doe", position="Developer", email="jane@example.com")
    PricingCard.objects.create(
        title="Starter",
        monthly_price="25 EUR",
        one_time_price="250 EUR",
        description="Basis",
    )

    response = client.get(reverse("home"))

    assert response.status_code == 200
    assert response.context["heroText"].title == "YooLink"
    assert list(response.context["FAQ"]) == list(FAQ.objects.all())
    assert response.context["teamMembers"].count() == 1
    assert response.context["pricing_cards"].count() == 1


def test_static_content_pages_render_without_cms_data(client):
    for url_name in [
        "kontakt",
        "leistungen_cms",
        "leistungen_logos",
        "leistungen_visitenkarte",
        "kunden",
        "leistungen",
    ]:
        response = client.get(reverse(url_name))
        assert response.status_code == 200


def test_logo_page_renders_cms_managed_content(client):
    TextContent.objects.create(
        name="main_logos_hero",
        header="Logo Studio",
        title="Dynamisches Logo Design",
        description="Diese Logo-Seite kommt aus dem CMS.",
        buttonText="Logo starten",
    )
    TextContent.objects.create(
        name="main_logos_bottomcta",
        title="Bereit für dein neues Logo?",
        description="Der CTA ist im CMS editierbar.",
        buttonText="Anfrage senden",
    )

    response = client.get(reverse("leistungen_logos"))

    assert response.status_code == 200
    assert response.context["textContent_hero"].title == "Dynamisches Logo Design"
    assert response.context["textContent_bottomcta"].buttonText == "Anfrage senden"
    assert b"Dynamisches Logo Design" in response.content
    assert b"Anfrage senden" in response.content


def _set_opening_hours(*rows):
    """Setzt die Oeffnungszeiten: (day, start, end[, pause_start, pause_end]).

    Bereits vorhandene Tage werden vorher entfernt - die Migration liefert die
    Buerozeiten der Genossenschaft mit, der Test bestimmt aber allein, was gilt.
    """
    site = WebsiteSettings.get_solo()
    OpeningHours.objects.filter(website=site).delete()
    for row in rows:
        day, start, end = row[:3]
        OpeningHours.objects.create(
            website=site,
            day=day,
            is_open=True,
            start_time=start,
            end_time=end,
            has_lunch_break=len(row) > 3,
            lunch_break_start=row[3] if len(row) > 3 else None,
            lunch_break_end=row[4] if len(row) > 3 else None,
        )


def test_opening_hours_fact_groups_days_and_drops_leading_zero():
    _set_opening_hours(
        ("MON", time(8, 0), time(12, 0)),
        ("WED", time(8, 0), time(12, 0)),
        ("FRI", time(8, 0), time(12, 0)),
    )

    assert opening_hours_fact() == {
        "title": "Mo / Mi / Fr",
        "description": "8:00 - 12:00 Uhr",
    }


def test_opening_hours_fact_collapses_consecutive_days_and_keeps_lunch_break():
    _set_opening_hours(
        *[
            (day, time(8, 0), time(16, 0), time(12, 0), time(13, 0))
            for day in ("MON", "TUE", "WED", "THU", "FRI")
        ]
    )

    assert opening_hours_fact() == {
        "title": "Mo - Fr",
        "description": "8:00 - 12:00 / 13:00 - 16:00 Uhr",
    }


def test_opening_hours_fact_is_none_without_open_days():
    _set_opening_hours()
    OpeningHours.objects.create(website=WebsiteSettings.get_solo(), day="MON", is_open=False)

    assert opening_hours_fact() is None


def test_home_fact_tile_shows_cms_opening_hours(client):
    _set_opening_hours(
        ("MON", time(8, 0), time(12, 0)),
        ("WED", time(8, 0), time(12, 0)),
        ("FRI", time(8, 0), time(12, 0)),
    )

    response = client.get(reverse("home"))

    assert response.status_code == 200
    assert response.context["bgp_opening_hours_auto"] is True
    assert response.context["bgp_fact_4"]["title"] == "Mo / Mi / Fr"
    assert response.context["bgp_fact_4"]["description"] == "8:00 - 12:00 Uhr"
    assert "8:00 - 12:00 Uhr".encode() in response.content


def test_home_fact_tile_falls_back_to_text_without_opening_hours(client):
    _set_opening_hours()
    TextContent.objects.create(name="main_bgp_fact_4", title="Nach Vereinbarung", description="Termin")

    response = client.get(reverse("home"))

    assert response.status_code == 200
    assert response.context["bgp_opening_hours_auto"] is False
    assert response.context["bgp_fact_4"]["title"] == "Nach Vereinbarung"


def test_home_aktuelles_teaser_shows_latest_blog_posts(client):
    author = UserFactory()
    for index in range(4):
        Blog.objects.create(
            title=f"Meldung {index}",
            slug=f"meldung-{index}",
            author=author,
            description=f"Beschreibung {index}",
            active=True,
            language="de",
        )
    Blog.objects.create(
        title="Noch nicht freigegeben",
        slug="entwurf",
        author=author,
        description="Entwurf",
        active=False,
        language="de",
    )

    response = client.get(reverse("home"))

    assert response.status_code == 200
    posts = response.context["bgp_home_news_posts"]
    assert len(posts) == 3
    assert all(post.active for post in posts)
    assert "Noch nicht freigegeben" not in response.content.decode()

    html = response.content.decode()
    for post in posts:
        assert post.title in html
        assert post.get_absolute_url() in html


def test_home_aktuelles_teaser_shows_empty_state_without_blog_posts(client):
    response = client.get(reverse("home"))

    assert response.status_code == 200
    assert response.context["bgp_home_news_posts"] == []
    assert "Zurzeit nichts Aktuelles" in response.content.decode()


def test_home_aktuelles_empty_state_text_is_cms_editable(client):
    TextContent.objects.create(
        name="main_bgp_home_news_empty",
        title="Keine Meldungen",
        description="Bald wieder mehr.",
    )

    response = client.get(reverse("home"))

    html = response.content.decode()
    assert "Keine Meldungen" in html
    assert "Bald wieder mehr." in html


def test_kontakt_teaser_uses_website_settings_and_opening_hours(client):
    site = WebsiteSettings.get_solo()
    site.company_name = "Baugenossenschaft Plattling eG"
    site.address = "Schillerstr. 6b, 94447 Plattling"
    site.tel_number = "09931 890073-0"
    site.fax_number = "09931 890073-9"
    site.contact_email = "info@bgp-test.de"
    site.save()
    _set_opening_hours(
        ("MON", time(8, 0), time(12, 0)),
        ("WED", time(8, 0), time(12, 0)),
        ("FRI", time(8, 0), time(12, 0)),
    )

    response = client.get(reverse("home"))
    html = response.content.decode()

    assert response.status_code == 200
    contact = response.context["bgp_contact"]
    assert contact["address_lines"] == ["Schillerstr. 6b", "94447 Plattling"]
    # Leerzeichen und Bindestrich duerfen nicht im tel:-Link landen.
    assert contact["tel_href"] == "tel:099318900730"

    assert "Schillerstr. 6b" in html
    assert "94447 Plattling" in html
    assert 'href="tel:099318900730"' in html
    assert "09931 890073-9" in html
    assert 'href="mailto:info@bgp-test.de"' in html
    assert "Mo / Mi / Fr" in html


def _clear_website_contact_details():
    """Leert die Kontaktfelder im Unternehmensprofil (die Migration fuellt sie vor)."""
    site = WebsiteSettings.get_solo()
    site.company_name = ""
    site.address = ""
    site.tel_number = ""
    site.fax_number = ""
    site.contact_email = ""
    site.save()


def test_kontakt_teaser_falls_back_to_page_text_without_website_settings(client):
    _clear_website_contact_details()
    TextContent.objects.create(name="main_bgp_contact_card_1", description="Adresse folgt")
    TextContent.objects.create(name="main_bgp_contact_card_3", description="E-Mail folgt")

    response = client.get(reverse("home"))
    html = response.content.decode()

    assert response.status_code == 200
    assert response.context["bgp_contact"]["tel"] == ""
    assert "Adresse folgt" in html
    assert "E-Mail folgt" in html
    # Ohne Telefonnummer verschwindet der zweite Button, statt leer dazustehen.
    assert 'href="tel:' not in html


def test_kontakt_page_shows_website_settings_and_opening_hours(client):
    site = WebsiteSettings.get_solo()
    site.company_name = "Baugenossenschaft Plattling eG"
    site.address = "Schillerstr. 6b, 94447 Plattling"
    site.tel_number = "09931 890073-0"
    site.fax_number = "09931 890073-9"
    site.contact_email = "info@bgp-test.de"
    site.save()
    _set_opening_hours(
        ("MON", time(8, 0), time(12, 0)),
        ("WED", time(8, 0), time(12, 0)),
        ("FRI", time(8, 0), time(12, 0)),
    )

    response = client.get(reverse("kontakt"))
    html = response.content.decode()

    assert response.status_code == 200
    # Kacheln im Kopfbereich, Anschriftskarte und Notfall-Button.
    assert 'href="tel:099318900730"' in html
    assert 'href="mailto:info@bgp-test.de"' in html
    assert "09931 890073-9" in html
    assert "Schillerstr. 6b" in html
    assert "94447 Plattling" in html
    # Oeffnungszeiten: Tabelle in der Karte und Kurzfassung in der Kachel.
    assert response.context["bgp_opening_hours_summary"] == "Mo / Mi / Fr · 8:00 - 12:00 Uhr"
    assert response.context["bgp_opening_hours_table"]["rows"] == [
        {"day": "Montag", "times": "08:00 - 12:00"},
        {"day": "Mittwoch", "times": "08:00 - 12:00"},
        {"day": "Freitag", "times": "08:00 - 12:00"},
    ]
    assert response.context["bgp_opening_hours_table"]["closed"] == "Di / Do / Sa / So"
    assert "Mittwoch" in html
    assert "Di / Do / Sa / So" in html
    # Routen-Button zeigt auf die hinterlegte Anschrift.
    assert "Schillerstr.+6b" in response.context["bgp_contact"]["maps_url"]
    assert "google.com/maps" in html


def test_kontakt_page_falls_back_to_page_texts_without_website_settings(client):
    _clear_website_contact_details()
    _set_opening_hours()
    TextContent.objects.create(name="main_bgp_contact_tile_1", description="Telefon folgt")
    TextContent.objects.create(name="main_bgp_contact_tile_2", description="E-Mail folgt")
    TextContent.objects.create(name="main_bgp_contact_tile_3", description="Zeiten folgen")
    TextContent.objects.create(name="main_bgp_contact_address", description="Anschrift folgt")
    TextContent.objects.create(name="main_bgp_contact_hours", description="Termine nach Vereinbarung")

    response = client.get(reverse("kontakt"))
    html = response.content.decode()

    assert response.status_code == 200
    for text in [
        "Telefon folgt",
        "E-Mail folgt",
        "Zeiten folgen",
        "Anschrift folgt",
        "Termine nach Vereinbarung",
    ]:
        assert text in html
    # Ohne Nummer bzw. Anschrift entfallen die Links, statt ins Leere zu zeigen.
    assert "tel:" not in html
    assert "google.com/maps" not in html


def test_kontakt_teaser_phone_href_keeps_international_prefix(client):
    site = WebsiteSettings.get_solo()
    site.tel_number = "+49 9931 890073-0"
    site.save()

    response = client.get(reverse("home"))

    assert response.context["bgp_contact"]["tel_href"] == "tel:+4999318900730"


def test_blog_list_and_detail_use_active_original_and_language_variant(client, settings):
    settings.LANGUAGE_CODE = "de"
    author = UserFactory()
    original = Blog.objects.create(
        title="Original Beitrag",
        slug="original-beitrag",
        author=author,
        body="Deutsch",
        active=True,
        language="de",
    )
    translation = Blog.objects.create(
        title="English Post",
        slug="english-post-en",
        author=author,
        body="English",
        active=True,
        language="en",
        original=original,
    )
    Blog.objects.create(
        title="Draft",
        slug="draft",
        author=author,
        body="Draft",
        active=False,
        language="de",
    )

    list_response = client.get(reverse("blog:blog"))
    assert list_response.status_code == 200
    assert list(list_response.context["blogs"]) == [original]

    detail_response = client.get(original.get_absolute_url())
    assert detail_response.status_code == 200
    assert detail_response.context["blog"] == original

    english_response = client.get(translation.get_absolute_url(), HTTP_ACCEPT_LANGUAGE="en")
    assert english_response.status_code in {200, 302}


def _news_post(author, number, active=True):
    return Blog.objects.create(
        title=f"Meldung {number}",
        slug=f"meldung-{number}",
        author=author,
        description=f"Beschreibung {number}",
        body=f"<p>Text {number}</p>",
        active=active,
        language="de",
    )


def test_aktuelles_url_has_no_trailing_slash_and_old_one_redirects(client):
    assert reverse("aktuelles") == "/aktuelles"

    assert client.get("/aktuelles").status_code == 200

    redirect = client.get("/aktuelles/")
    assert redirect.status_code == 301
    assert redirect["Location"] == "/aktuelles"


def test_aktuelles_lists_blog_posts_with_lead_and_pagination(client):
    author = UserFactory()
    for number in range(12):
        _news_post(author, number)
    hidden = _news_post(author, 99, active=False)

    response = client.get("/aktuelles")
    html = response.content.decode()

    assert response.status_code == 200
    assert response.context["news_total"] == 12
    assert hidden.title not in html

    lead = response.context["news_lead"]
    page = response.context["news_page"]
    assert lead is not None
    # Die Top-Meldung darf nicht zusaetzlich als Kachel auftauchen.
    assert lead not in page.object_list
    assert len(page.object_list) == 9
    assert lead.get_absolute_url() in html
    assert "Seite 1 von 2" in html

    second = client.get("/aktuelles?page=2")
    assert len(second.context["news_page"].object_list) == 2


def test_aktuelles_shows_empty_state_without_posts(client):
    response = client.get("/aktuelles")

    assert response.status_code == 200
    assert response.context["news_lead"] is None
    assert "Zurzeit nichts Aktuelles" in response.content.decode()


def test_aktuelles_detail_is_the_canonical_url_of_a_post(client):
    author = UserFactory()
    post = _news_post(author, 1)

    assert post.get_absolute_url() == f"/aktuelles/{post.pk}-{post.slug}"

    response = client.get(post.get_absolute_url())
    html = response.content.decode()
    assert response.status_code == 200
    assert post.title in html
    # Beitragstext wird im Rich-Text-Container gerendert
    assert "rich-text" in html
    assert "Zurück zur Übersicht" in html

    # Die alte /blog/-Adresse zeigt dauerhaft auf die neue, sonst gaebe es die
    # Meldung unter zwei URLs.
    old = client.get(f"/blog/{post.pk}-{post.slug}/")
    assert old.status_code == 301
    assert old["Location"] == post.get_absolute_url()


def test_aktuelles_detail_hides_unpublished_posts(client):
    author = UserFactory()
    hidden = _news_post(author, 1, active=False)

    assert client.get(hidden.get_absolute_url()).status_code == 404
