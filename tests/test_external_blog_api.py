from datetime import timedelta
from io import BytesIO
import json
from urllib.parse import parse_qs, urlparse

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from PIL import Image
from rest_framework.test import APIClient

from yoolink.users.tests.factories import UserFactory
from yoolink.ycms.models import Blog, DeveloperApiConnectAuthorization, DeveloperApiKey, UserSettings, fileentry

pytestmark = pytest.mark.django_db


@pytest.fixture
def cms_user():
    user = UserFactory(email="api-owner@example.com")
    user.set_password("password12345")
    user.save(update_fields=["password", "email"])
    UserSettings.objects.create(
        user=user,
        email=user.email,
        full_name="API Owner",
        company_name="YooLink Test",
    )
    return user


def issue_key(user, access_level=DeveloperApiKey.WRITE, expires_at=None):
    return DeveloperApiKey.issue_key(
        created_by=user,
        name="Content Automation",
        access_level=access_level,
        allowed_apps=[DeveloperApiKey.APP_BLOG],
        expires_at=expires_at,
    )


def api_client_for(raw_key):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {raw_key}")
    return client


def image_upload(name="blog-image.png"):
    buffer = BytesIO()
    Image.new("RGB", (16, 16), color="blue").save(buffer, format="PNG")
    buffer.seek(0)
    return SimpleUploadedFile(name, buffer.read(), content_type="image/png")


def test_developer_settings_creates_one_time_api_key(client, cms_user):
    client.force_login(cms_user)

    response = client.post(
        reverse("ycms:developer-settings"),
        {
            "action": "create",
            "name": "External AI Platform",
            "access_level": DeveloperApiKey.WRITE,
            "allowed_apps": [DeveloperApiKey.APP_BLOG],
            "expires_in": "never",
        },
    )

    assert response.status_code == 200
    assert DeveloperApiKey.objects.filter(created_by=cms_user).count() == 1
    assert b"yl_live_" in response.content
    assert reverse("ycms:developer-api-docs").encode() in response.content
    assert b"http://testserver/api/cms/blog/" in response.content
    assert b"http://testserver/api/ping/" in response.content
    assert b"http://testserver/api/schema/" in response.content


def test_developer_api_docs_requires_login_and_documents_blog_api(client, cms_user):
    response = client.get(reverse("ycms:developer-api-docs"))
    assert response.status_code == 302

    client.force_login(cms_user)
    response = client.get(reverse("ycms:developer-api-docs"))

    assert response.status_code == 200
    assert b"/api/cms/blog/" in response.content
    assert b"http://testserver/api/cms/" in response.content
    assert b"http://testserver/api/ping/" in response.content
    assert b"http://testserver/api/schema/" in response.content
    assert b"Authorization: Bearer" in response.content
    assert b"POST" in response.content


def test_developer_api_ping_requires_and_confirms_auth(cms_user):
    unauthenticated_client = APIClient()
    unauthenticated_response = unauthenticated_client.get("/api/ping/")

    _, raw_key = issue_key(cms_user, access_level=DeveloperApiKey.READ)
    authenticated_client = api_client_for(raw_key)
    authenticated_response = authenticated_client.get("/api/ping/")

    assert unauthenticated_response.status_code == 401
    assert authenticated_response.status_code == 200
    assert authenticated_response.data["ok"] is True
    assert authenticated_response.data["authenticated"] is True
    assert authenticated_response.data["user"] == cms_user.username
    assert "api_key" not in authenticated_response.data
    assert authenticated_response.data["access_level"] == DeveloperApiKey.READ
    assert authenticated_response.data["allowed_apps"] == [DeveloperApiKey.APP_BLOG]


def test_developer_connect_flow_issues_api_key_with_pkce(client, cms_user):
    client.force_login(cms_user)
    redirect_uri = "https://ai.example.com/api/yoolink/callback"
    code_verifier = "a" * 64
    code_challenge = DeveloperApiConnectAuthorization.pkce_s256(code_verifier)
    connect_params = {
        "client_name": "YooLink AI",
        "redirect_uri": redirect_uri,
        "state": "opaque-state",
        "scope": DeveloperApiKey.APP_BLOG,
        "access_level": DeveloperApiKey.WRITE,
        "code_challenge": code_challenge,
        "code_challenge_method": DeveloperApiConnectAuthorization.METHOD_S256,
    }

    authorize_page = client.get(reverse("ycms:developer-connect"), connect_params)
    assert authorize_page.status_code == 200
    assert b"YooLink AI" in authorize_page.content

    authorize_response = client.post(
        reverse("ycms:developer-connect"),
        {**connect_params, "action": "authorize"},
    )
    assert authorize_response.status_code == 302
    redirect = urlparse(authorize_response["Location"])
    query = parse_qs(redirect.query)
    code = query["code"][0]

    assert f"{redirect.scheme}://{redirect.netloc}{redirect.path}" == redirect_uri
    assert query["state"][0] == "opaque-state"
    assert code.startswith("yl_connect_")

    api_client = APIClient()
    token_response = api_client.post(
        "/api/connect/token/",
        {
            "grant_type": "authorization_code",
            "code": code,
            "code_verifier": code_verifier,
            "redirect_uri": redirect_uri,
        },
        format="json",
    )

    assert token_response.status_code == 200
    assert token_response.data["token_type"] == "Bearer"
    assert token_response.data["api_key"].startswith("yl_live_")
    assert token_response.data["access_level"] == DeveloperApiKey.WRITE
    assert token_response.data["allowed_apps"] == [DeveloperApiKey.APP_BLOG]
    assert DeveloperApiKey.objects.filter(created_by=cms_user, name="YooLink AI Connect").count() == 1

    ping_client = api_client_for(token_response.data["api_key"])
    ping_response = ping_client.get("/api/ping/")
    assert ping_response.status_code == 200

    reused_response = api_client.post(
        "/api/connect/token/",
        {
            "grant_type": "authorization_code",
            "code": code,
            "code_verifier": code_verifier,
            "redirect_uri": redirect_uri,
        },
        format="json",
    )
    assert reused_response.status_code == 400
    assert reused_response.data["error"] == "invalid_grant"


def test_developer_connect_rejects_wrong_pkce_verifier(client, cms_user):
    client.force_login(cms_user)
    redirect_uri = "https://ai.example.com/api/yoolink/callback"
    connect_params = {
        "client_name": "YooLink AI",
        "redirect_uri": redirect_uri,
        "scope": DeveloperApiKey.APP_BLOG,
        "access_level": DeveloperApiKey.READ,
        "code_challenge": DeveloperApiConnectAuthorization.pkce_s256("b" * 64),
        "code_challenge_method": DeveloperApiConnectAuthorization.METHOD_S256,
    }
    authorize_response = client.post(
        reverse("ycms:developer-connect"),
        {**connect_params, "action": "authorize"},
    )
    code = parse_qs(urlparse(authorize_response["Location"]).query)["code"][0]

    token_response = APIClient().post(
        "/api/connect/token/",
        {
            "grant_type": "authorization_code",
            "code": code,
            "code_verifier": "c" * 64,
            "redirect_uri": redirect_uri,
        },
        format="json",
    )

    assert token_response.status_code == 400
    assert token_response.data["error"] == "invalid_grant"
    assert not DeveloperApiKey.objects.filter(created_by=cms_user, name="YooLink AI Connect").exists()


def test_read_only_key_can_read_blogs_but_cannot_create(cms_user):
    Blog.objects.create(
        title="Existing Blog",
        description="Existing description",
        body="<p>Existing body</p>",
        code=[],
        active=True,
        author=cms_user,
    )
    _, raw_key = issue_key(cms_user, access_level=DeveloperApiKey.READ)
    client = api_client_for(raw_key)

    list_response = client.get("/api/cms/blog/")
    create_response = client.post(
        "/api/cms/blog/",
        {
            "title": "Blocked Blog",
            "description": "Should not be created",
            "body": "<p>Nope</p>",
        },
        format="json",
    )

    assert list_response.status_code == 200
    assert list_response.data[0]["title"] == "Existing Blog"
    assert "body" not in list_response.data[0]
    assert "markdown" not in list_response.data[0]
    assert "code" not in list_response.data[0]
    assert "translations" not in list_response.data[0]
    assert list_response.data[0]["api_url"].endswith(f"/api/cms/blog/{Blog.objects.get().id}/")
    assert create_response.status_code == 403
    assert not Blog.objects.filter(title="Blocked Blog").exists()


def test_write_key_creates_and_updates_blog(cms_user):
    _, raw_key = issue_key(cms_user)
    client = api_client_for(raw_key)

    create_response = client.post(
        "/api/cms/blog/",
        {
            "title": "KI Event Rueckblick",
            "description": "Automatisch erzeugter Rueckblick.",
            "body": "<p>Der Event war stark besucht.</p>",
            "active": True,
            "language": "de",
        },
        format="json",
    )

    assert create_response.status_code == 201
    blog = Blog.objects.get(title="KI Event Rueckblick")
    assert blog.author == cms_user
    assert blog.active is True
    assert blog.code[0]["name"] == "textArea"

    update_response = client.patch(
        f"/api/cms/blog/{blog.id}/",
        {"active": False, "description": "Aktualisierte Beschreibung."},
        format="json",
    )

    assert update_response.status_code == 200
    blog.refresh_from_db()
    assert blog.active is False
    assert blog.description == "Aktualisierte Beschreibung."


def test_write_key_can_create_blog_from_markdown(cms_user):
    _, raw_key = issue_key(cms_user)
    client = api_client_for(raw_key)

    response = client.post(
        "/api/cms/blog/",
        {
            "title": "Markdown Blog",
            "description": "Markdown Beschreibung.",
            "markdown": "## Einleitung\n\nDas ist **fett** und [verlinkt](https://example.com).",
            "active": True,
            "language": "de",
        },
        format="json",
    )

    assert response.status_code == 201
    blog = Blog.objects.get(title="Markdown Blog")
    assert blog.markdown.startswith("## Einleitung")
    assert "<h2" in blog.body
    assert "<strong>fett</strong>" in blog.body
    assert [block["name"] for block in blog.code] == ["title-1", "textArea"]
    assert blog.code[0]["type"] == "h2"
    assert blog.code[0]["value"] == "Einleitung"
    assert response.data["markdown"] == blog.markdown


def test_markdown_is_split_into_builder_blocks(cms_user):
    _, raw_key = issue_key(cms_user)
    client = api_client_for(raw_key)

    response = client.post(
        "/api/cms/blog/",
        {
            "title": "Strukturierter Markdown Blog",
            "description": "Markdown mit mehreren Builder Elementen.",
            "markdown": (
                "## Abschnitt\n\n"
                "Ein kurzer Absatz mit **Fettschrift**.\n\n"
                "![Buehne](https://example.com/event.png)\n\n"
                "### Details\n\n"
                "- Punkt eins\n"
                "- Punkt zwei\n\n"
                "```python\nprint('hi')\n```"
            ),
            "active": True,
            "language": "de",
        },
        format="json",
    )

    assert response.status_code == 201
    blog = Blog.objects.get(title="Strukturierter Markdown Blog")
    assert [block["name"] for block in blog.code] == ["title-1", "textArea", "image", "title-2", "textArea", "code"]
    assert blog.code[2]["attributes"]["src"] == "https://example.com/event.png"
    assert blog.code[2]["attributes"]["alt"] == "Buehne"
    assert blog.code[5]["attributes"]["class"].endswith("language-python")
    assert "![Buehne](https://example.com/event.png)" in blog.markdown


def test_markdown_groups_section_text_into_one_builder_textarea(cms_user):
    _, raw_key = issue_key(cms_user)
    client = api_client_for(raw_key)

    response = client.post(
        "/api/cms/blog/",
        {
            "title": "Gruppierter Markdown Blog",
            "description": "Markdown bleibt im Builder kompakt.",
            "markdown": (
                "### Vom Entwurf zum fertigen Artikel\n\n"
                "Der wichtigste Schritt ist eine klare Trennung: Titel und Beschreibung werden im CMS gepflegt, "
                "der eigentliche Artikel kommt als Markdown in den Editor.\n\n"
                "Ein typischer Ablauf sieht so aus:\n\n"
                "- Thema und Zielgruppe festlegen\n"
                "- Artikelstruktur mit Zwischenüberschriften erstellen\n"
                "- Text als Markdown schreiben oder einfügen\n\n"
                "### Warum Bilder eine eigene Rolle spielen\n\n"
                "Bilder sollten über die CMS-Mediathek gespeichert werden."
            ),
            "active": True,
            "language": "de",
        },
        format="json",
    )

    assert response.status_code == 201
    blog = Blog.objects.get(title="Gruppierter Markdown Blog")
    assert [block["name"] for block in blog.code] == ["title-2", "textArea", "title-2", "textArea"]
    assert blog.code[1]["value"].count("<p>") == 2
    assert "<ul" in blog.code[1]["value"]
    assert blog.code[1]["value"].count("<li>") == 3


def test_markdown_image_options_are_rendered_and_preserved(cms_user):
    _, raw_key = issue_key(cms_user)
    client = api_client_for(raw_key)

    response = client.post(
        "/api/cms/blog/",
        {
            "title": "Markdown Bildgröße",
            "description": "Markdown Bild mit Größe.",
            "markdown": "## Bild\n\n![Buehne](https://example.com/event.png){width=50% height=320px}",
            "active": True,
            "language": "de",
        },
        format="json",
    )

    assert response.status_code == 201
    blog = Blog.objects.get(title="Markdown Bildgröße")
    assert 'style="width: 50%; height: 320px"' in blog.body
    assert blog.code[1]["css"] == {"height": "320px", "width": "50%"}
    assert "![Buehne](https://example.com/event.png){width=50% height=320px}" in blog.markdown


def test_markdown_gallery_block_renders_and_maps_to_builder(cms_user):
    _, raw_key = issue_key(cms_user)
    client = api_client_for(raw_key)

    response = client.post(
        "/api/cms/blog/",
        {
            "title": "Markdown Galerie",
            "description": "Markdown Galerie mit Bildern.",
            "markdown": (
                "## Bilder\n\n"
                ":::gallery{height=240px}\n"
                "![Erstes Bild](https://example.com/one.png)\n"
                "![Zweites Bild](https://example.com/two.png)\n"
                ":::"
            ),
            "active": True,
            "language": "de",
        },
        format="json",
    )

    assert response.status_code == 201
    blog = Blog.objects.get(title="Markdown Galerie")
    assert [block["name"] for block in blog.code] == ["title-1", "galery"]
    assert blog.code[1]["images"] == ["https://example.com/one.png", "https://example.com/two.png"]
    assert blog.code[1]["imageAlts"] == ["Erstes Bild", "Zweites Bild"]
    assert blog.code[1]["css"] == {"height": "240px", "width": "100%"}
    assert 'class="carousel rounded-lg !w-full"' in blog.body
    assert 'src="https://example.com/two.png"' in blog.body


def test_markdown_special_builder_shortcodes_render_and_map_to_builder(cms_user):
    _, raw_key = issue_key(cms_user)
    client = api_client_for(raw_key)

    response = client.post(
        "/api/cms/blog/",
        {
            "title": "Markdown Builder Elemente",
            "description": "Markdown mit Video und Datei.",
            "markdown": (
                "## Medien\n\n"
                "::youtube{url=https://youtu.be/dQw4w9WgXcQ title=\"Produktvideo\" height=360px}\n\n"
                "::video{src=/media/yoolink/videos/demo.mp4 poster=/media/yoolink/images/poster.jpg title=\"CMS Video\" alt=\"Video Demo\" controls preload=metadata width=100% height=420px}\n\n"
                "::file{href=/media/yoolink/files/guide.pdf title=\"Guide herunterladen\" ext=.pdf}"
            ),
            "active": True,
            "language": "de",
        },
        format="json",
    )

    assert response.status_code == 201
    blog = Blog.objects.get(title="Markdown Builder Elemente")
    assert [block["name"] for block in blog.code] == ["title-1", "yt-video", "video", "file"]
    assert blog.code[1]["attributes"]["src"] == "https://www.youtube.com/embed/dQw4w9WgXcQ"
    assert blog.code[1]["attributes"]["loading"] == "lazy"
    assert blog.code[2]["attributes"]["controls"] == "controls"
    assert blog.code[2]["attributes"]["data-alt_text"] == "Video Demo"
    assert blog.code[3]["attributes"]["rel"] == "noopener"
    assert "<iframe" in blog.body
    assert "<video" in blog.body
    assert "Guide herunterladen" in blog.body


def test_write_key_can_upload_blog_media_and_use_markdown(cms_user):
    _, raw_key = issue_key(cms_user)
    client = api_client_for(raw_key)

    upload_response = client.post(
        "/api/cms/blog/media/",
        {
            "file": image_upload(),
            "title": "Event Bild",
            "alt_text": "Volles Haus beim Event",
        },
        format="multipart",
    )

    assert upload_response.status_code == 201
    assert fileentry.objects.filter(title="Event Bild").exists()
    assert upload_response.data["markdown"].startswith("![Volles Haus beim Event](")
    assert upload_response.data["url"].endswith(".png")

    create_response = client.post(
        "/api/cms/blog/",
        {
            "title": "Blog mit Bild",
            "description": "Beschreibung mit Bild.",
            "markdown": f"## Galerie\n\n{upload_response.data['markdown']}",
            "title_image_media_id": upload_response.data["id"],
            "active": True,
            "language": "de",
        },
        format="json",
    )

    assert create_response.status_code == 201
    blog = Blog.objects.get(title="Blog mit Bild")
    assert blog.title_image
    assert create_response.data["title_image_url"].endswith(".png")
    assert upload_response.data["markdown"] in blog.markdown
    assert [block["name"] for block in blog.code] == ["title-1", "image"]
    assert 'class="rounded-2xl my-4"' in blog.body


@override_settings(YCMS_UPLOAD_LIMIT_BYTES={"image": 4})
def test_write_key_rejects_oversized_blog_media(cms_user):
    _, raw_key = issue_key(cms_user)
    client = api_client_for(raw_key)

    response = client.post(
        "/api/cms/blog/media/",
        {"file": image_upload("too-large.png")},
        format="multipart",
    )

    assert response.status_code == 400
    assert "zu gross" in str(response.data)
    assert fileentry.objects.count() == 0


def test_read_only_key_cannot_upload_blog_media(cms_user):
    _, raw_key = issue_key(cms_user, access_level=DeveloperApiKey.READ)
    client = api_client_for(raw_key)

    response = client.post(
        "/api/cms/blog/media/",
        {"file": image_upload()},
        format="multipart",
    )

    assert response.status_code == 403
    assert fileentry.objects.count() == 0


def test_cms_builder_create_stores_markdown(client, cms_user):
    client.force_login(cms_user)
    response = client.post(
        reverse("ycms:blog-create"),
        {
            "title": "Builder Markdown Blog",
            "description": "Builder Beschreibung.",
            "body": '<div><h2 class="text-2xl">Builder Titel</h2><p>Builder Text</p></div>',
            "code": '[{"name":"title-1","type":"h2","value":"Builder Titel"},{"name":"textArea","type":"p","value":"<p>Builder Text</p>"}]',
            "active": "true",
        },
    )

    assert response.status_code == 201
    blog = Blog.objects.get(title="Builder Markdown Blog")
    assert "## Builder Titel" in blog.markdown
    assert "Builder Text" in blog.markdown


def test_cms_markdown_editor_pages_include_image_dialog(client, cms_user):
    client.force_login(cms_user)
    blog = Blog.objects.create(
        title="Dialog Blog",
        description="Dialog Beschreibung.",
        body="<p>Text</p>",
        markdown="## Text",
        code=[],
        author=cms_user,
    )

    add_response = client.get(reverse("ycms:blog-add"))
    edit_response = client.get(reverse("ycms:blog-details", args=[blog.id]))

    assert add_response.status_code == 200
    assert edit_response.status_code == 200
    assert b'id="openMarkdownImageModal"' in add_response.content
    assert b'id="markdownImageModal"' in add_response.content
    assert b'id="openMarkdownMediaModal"' in add_response.content
    assert b'id="markdownMediaModal"' in add_response.content
    assert b'id="openMarkdownImageModal"' in edit_response.content
    assert b'id="markdownImageModal"' in edit_response.content
    assert b'id="openMarkdownMediaModal"' in edit_response.content
    assert b'id="markdownMediaModal"' in edit_response.content


def test_cms_markdown_create_renders_body_and_builder_code(client, cms_user):
    client.force_login(cms_user)

    response = client.post(
        reverse("ycms:blog-create"),
        {
            "title": "CMS Markdown Blog",
            "description": "Direkt im CMS eingefuegt.",
            "content_source": "markdown",
            "markdown": "## CMS Abschnitt\n\nText aus Markdown.\n\n![Alt Text](/media/yoolink/images/bild.png)",
            "active": "true",
        },
    )

    assert response.status_code == 201
    blog = Blog.objects.get(title="CMS Markdown Blog")
    assert blog.markdown.startswith("## CMS Abschnitt")
    assert "<h2" in blog.body
    assert 'src="/media/yoolink/images/bild.png"' in blog.body
    assert [block["name"] for block in blog.code] == ["title-1", "textArea", "image"]
    assert blog.active is True


def test_cms_markdown_update_regenerates_body_and_builder_code(client, cms_user):
    client.force_login(cms_user)
    blog = Blog.objects.create(
        title="Alter CMS Blog",
        description="Alte Beschreibung.",
        body="<p>Alt</p>",
        markdown="Alt",
        code=[],
        author=cms_user,
    )

    response = client.post(
        reverse("ycms:blog-update", args=[blog.id]),
        {
            "title": "Neuer CMS Blog",
            "description": "Neue Beschreibung.",
            "content_source": "markdown",
            "markdown": "### Neue Ebene\n\n- Punkt eins\n- Punkt zwei",
            "active": "false",
        },
    )

    assert response.status_code == 201
    blog.refresh_from_db()
    assert blog.title == "Neuer CMS Blog"
    assert blog.markdown == "### Neue Ebene\n\n- Punkt eins\n- Punkt zwei"
    assert "<h3" in blog.body
    assert "<li>Punkt eins</li>" in blog.body
    assert [block["name"] for block in blog.code] == ["title-2", "textArea"]
    assert blog.active is False


def test_cms_markdown_preview_uses_blog_renderer(client, cms_user):
    client.force_login(cms_user)

    response = client.post(
        reverse("ycms:blog-markdown-preview"),
        {"markdown": "## Preview\n\nDas ist **fett**."},
    )

    assert response.status_code == 200
    payload = response.json()
    assert "<h2" in payload["body"]
    assert "<strong>fett</strong>" in payload["body"]
    assert payload["code"][0]["name"] == "title-1"


def test_cms_builder_code_can_be_converted_to_markdown_for_editor_sync(client, cms_user):
    client.force_login(cms_user)

    response = client.post(
        reverse("ycms:blog-code-to-markdown"),
        {
            "code": json.dumps([
                {"name": "title-1", "type": "h2", "value": "Builder Abschnitt"},
                {"name": "textArea", "type": "p", "value": "<p>Builder Text</p>"},
                {
                    "name": "image",
                    "type": "img",
                    "attributes": {"src": "/media/yoolink/images/bild.png", "alt": "Bild"},
                    "css": {"width": "50%", "height": "auto"},
                },
                {
                    "name": "yt-video",
                    "type": "iframe",
                    "attributes": {"src": "https://www.youtube.com/embed/video-id", "title": "Video"},
                    "css": {"width": "100%", "height": "315px"},
                },
                {
                    "name": "file",
                    "type": "a",
                    "attributes": {"href": "/media/yoolink/files/guide.pdf", "title": "Guide", "data-ext": ".pdf"},
                    "value": "Guide",
                },
            ]),
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert "## Builder Abschnitt" in payload["markdown"]
    assert "Builder Text" in payload["markdown"]
    assert "![Bild](/media/yoolink/images/bild.png){width=50%}" in payload["markdown"]
    assert "::youtube" in payload["markdown"]
    assert "::file" in payload["markdown"]
    assert "<h2" in payload["body"]


def test_blog_detail_includes_language_variant_links(cms_user):
    root = Blog.objects.create(
        title="Deutscher Blog",
        description="Deutsche Beschreibung.",
        body="<p>Deutsch</p>",
        code=[],
        active=True,
        language="de",
        author=cms_user,
    )
    translation = Blog.objects.create(
        title="English Blog",
        description="English description.",
        body="<p>English</p>",
        code=[],
        active=False,
        language="en",
        original=root,
        slug="english-blog-en",
        author=cms_user,
    )
    _, raw_key = issue_key(cms_user)
    client = api_client_for(raw_key)

    response = client.get(f"/api/cms/blog/{root.id}/")

    assert response.status_code == 200
    translations = response.data["translations"]
    assert {item["language"] for item in translations} == {"de", "en"}
    assert translations[0]["is_original"] is True
    assert any(
        item["id"] == translation.id and item["api_url"].endswith(f"/api/cms/blog/{translation.id}/")
        for item in translations
    )


def test_creating_duplicate_language_variant_is_rejected(cms_user):
    root = Blog.objects.create(
        title="Original Blog",
        description="Original description.",
        body="<p>Deutsch</p>",
        code=[],
        active=True,
        language="de",
        author=cms_user,
    )
    Blog.objects.create(
        title="English Blog",
        description="English description.",
        body="<p>English</p>",
        code=[],
        active=False,
        language="en",
        original=root,
        slug="english-blog-en",
        author=cms_user,
    )
    _, raw_key = issue_key(cms_user)
    client = api_client_for(raw_key)

    response = client.post(
        "/api/cms/blog/",
        {
            "title": "Another English Blog",
            "description": "Another description.",
            "body": "<p>Duplicate</p>",
            "language": "en",
            "original": root.id,
        },
        format="json",
    )

    assert response.status_code == 400
    assert root.translations.filter(language="en").count() == 1


def test_expired_key_is_rejected(cms_user):
    _, raw_key = issue_key(
        cms_user,
        expires_at=timezone.now() - timedelta(minutes=1),
    )
    client = api_client_for(raw_key)

    response = client.get("/api/cms/blog/")

    assert response.status_code == 401
