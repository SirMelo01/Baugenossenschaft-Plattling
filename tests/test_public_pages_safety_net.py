import pytest
from django.urls import reverse

from yoolink.users.tests.factories import UserFactory
from yoolink.ycms.applications.content.models import TextContent
from yoolink.ycms.models import Blog, FAQ, PricingCard, TeamMember

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
