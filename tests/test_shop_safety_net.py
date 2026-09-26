import json
import re
from decimal import Decimal

import pytest
from django.core import mail
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from django.utils.html import escape
from rest_framework.test import APIClient

from yoolink.users.tests.factories import UserFactory
from yoolink.ycms.applications.shop.models import (
    ProductGroup,
    ShopSettings,
    Category,
    Order,
    OrderItem,
    Product,
    ProductSpecification,
    ShippingAddress,
)
from yoolink.ycms.applications.notifications.models import Notification
from yoolink.ycms.models import (
    AnyFile,
    CMSRole,
    CMSUserRole,
    OWNER_PERMISSIONS,
    UserSettings,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def cms_user():
    user = UserFactory(email="shop-owner@example.com")
    user.set_password("password12345")
    user.save(update_fields=["password", "email"])
    UserSettings.objects.create(
        user=user,
        email=user.email,
        full_name="Shop Owner",
        company_name="YooLink Shop",
        tel_number="09999 123",
    )
    role = CMSRole.objects.create(
        name="Test Owner",
        slug="test-owner",
        permissions=OWNER_PERMISSIONS,
        is_system=False,
    )
    CMSUserRole.objects.create(user=user, role=role)
    return user


@pytest.fixture
def logged_in_client(cms_user):
    from django.test import Client

    client = Client()
    client.force_login(cms_user)
    return client


def _product_payload(**overrides):
    payload = {
        "title": "Test Produkt",
        "description": "Ein Produkt für Tests",
        "address": "Schillerstr. 6b, 94447 Plattling",
        "selected_categories": json.dumps(["CMS", "Hosting"]),
        "selected_file_ids": "[]",
        "specifications": json.dumps(
            [
                {"key": "Material", "value": "Code", "sort_order": 0},
                {"key": "Version", "value": "1.0", "sort_order": 1},
            ]
        ),
        "price": "49.90",
        "weight": "1.5000",
        "isActive": "true",
        "isInStock": "true",
        "isOnlineAvailable": "true",
        "isReduced": "false",
        "isShowcaseOnly": "false",
        "showPriceWhenShowcase": "true",
    }
    payload.update(overrides)
    return payload


def _create_product(**overrides):
    category, _ = Category.objects.get_or_create(name=overrides.pop("category_name", "CMS"))
    product = Product.objects.create(
        title=overrides.pop("title", "Test Produkt"),
        description=overrides.pop("description", "Beschreibung"),
        price=overrides.pop("price", Decimal("49.90")),
        weight=overrides.pop("weight", Decimal("1.5000")),
        is_active=overrides.pop("is_active", True),
        is_in_stock=overrides.pop("is_in_stock", True),
        online_sell=overrides.pop("online_sell", True),
        is_reduced=overrides.pop("is_reduced", False),
        discount_price=overrides.pop("discount_price", None),
        showcase_only=overrides.pop("showcase_only", False),
        show_price_when_showcase=overrides.pop("show_price_when_showcase", True),
        **overrides,
    )
    product.categories.add(category)
    return product


def test_product_model_enforces_discount_and_showcase_rules():
    product = _create_product(
        title="Rabatt Produkt",
        is_reduced=True,
        discount_price=Decimal("39.90"),
        showcase_only=True,
        online_sell=True,
    )

    product.refresh_from_db()
    # showcase_only und online_sell ("Lieferung möglich") sind bewusst entkoppelt:
    # ein Showcase-Produkt darf weiterhin als lieferbar markiert sein.
    assert product.online_sell is True
    assert product.effective_price == Decimal("49.90")
    assert product.should_show_purchase_controls is False

    product.discount_price = Decimal("59.90")
    with pytest.raises(ValidationError):
        product.full_clean()


def test_order_totals_shipping_tax_and_notifications():
    product = _create_product(price=Decimal("10.00"), weight=Decimal("1.0000"))
    address = ShippingAddress.objects.create(
        prename="Max",
        name="Mustermann",
        address="Teststrasse 1",
        city="Berlin",
        postal_code="10115",
        country="Deutschland",
    )
    order = Order.objects.create(
        buyer_email="buyer@example.com",
        buyer_address=address,
        verified=True,
        shipping=Order.ShippingMethod.SHIPPING,
    )
    OrderItem.objects.create(order=order, product=product, quantity=3, unit_price=product.price)

    assert order.subtotal_gross() == Decimal("30.00")
    assert order.shipping_price() == Decimal("6.99")
    assert order.total() == Decimal("36.99")
    assert order.total_quantity() == 3

    notification = Notification.objects.get(order=order)
    assert notification.priority == Notification.Priority.NORMAL
    assert "Neue Bestellung" in notification.title


def test_cms_product_create_search_update_and_delete(logged_in_client):
    create_response = logged_in_client.post(
        reverse("ycms:product-create-upload"),
        _product_payload(),
    )
    assert create_response.status_code == 201

    product = Product.objects.get()
    assert product.slug == "test-produkt"
    # Die Anschrift wird frei eingetippt und steht direkt an der Immobilie.
    assert product.address == "Schillerstr. 6b, 94447 Plattling"
    assert list(product.categories.values_list("name", flat=True)) == []
    assert list(ProductSpecification.objects.values_list("key", "value")) == []

    search_response = logged_in_client.get(
        reverse("ycms:product_search"),
        {"q": "Produkt", "availability": "online"},
    )
    assert search_response.status_code == 200
    assert search_response.json()["pagination"]["total_count"] == 1

    address_search_response = logged_in_client.get(
        reverse("ycms:product_search"),
        {"q": "Schillerstr"},
    )
    assert address_search_response.status_code == 200
    assert address_search_response.json()["pagination"]["total_count"] == 1

    update_response = logged_in_client.post(
        reverse("ycms:product-detail-update", args=[product.id, product.slug]),
        _product_payload(title="Geändertes Produkt", isReduced="true", reducedPrice="39.90"),
    )
    assert update_response.status_code == 200
    product.refresh_from_db()
    assert product.title == "Geändertes Produkt"
    assert product.is_reduced is False
    assert product.discount_price is None

    delete_response = logged_in_client.post(
        reverse("ycms:product-detail-delete", args=[product.id, product.slug])
    )
    assert delete_response.status_code == 200
    assert Product.objects.count() == 0


def test_cms_product_create_ignores_removed_discount_price(logged_in_client):
    response = logged_in_client.post(
        reverse("ycms:product-create-upload"),
        _product_payload(isReduced="true", reducedPrice="39.90"),
    )

    assert response.status_code == 201
    product = Product.objects.get()
    assert product.is_reduced is False
    assert product.discount_price is None


def test_cms_product_create_ignores_reduced_price_when_switch_is_off(logged_in_client):
    response = logged_in_client.post(
        reverse("ycms:product-create-upload"),
        _product_payload(reducedPrice="39.90"),
    )

    assert response.status_code == 201
    product = Product.objects.get()
    assert product.is_reduced is False
    assert product.discount_price is None


def test_cms_product_create_allows_blank_price_and_living_area(logged_in_client):
    response = logged_in_client.post(
        reverse("ycms:product-create-upload"),
        _product_payload(price="", weight=""),
    )

    assert response.status_code == 201
    product = Product.objects.get()
    assert product.price is None
    assert product.weight == Decimal("0.0000")


@override_settings(YCMS_UPLOAD_LIMIT_BYTES={"image": 4})
def test_cms_product_create_rejects_oversized_title_image(logged_in_client):
    response = logged_in_client.post(
        reverse("ycms:product-create-upload"),
        _product_payload(
            title_image=SimpleUploadedFile(
                "too-large.png",
                b"12345",
                content_type="image/png",
            )
        ),
    )

    assert response.status_code == 400
    assert "zu gross" in response.json()["error"]
    assert Product.objects.count() == 0


def test_cms_product_update_can_disable_discount_with_stale_reduced_price(logged_in_client):
    product = _create_product(is_reduced=True, discount_price=Decimal("39.90"))

    response = logged_in_client.post(
        reverse("ycms:product-detail-update", args=[product.id, product.slug]),
        _product_payload(isReduced="false", reducedPrice="39.90"),
    )

    assert response.status_code == 200
    product.refresh_from_db()
    assert product.is_reduced is False
    assert product.discount_price is None


def test_cms_product_create_ignores_removed_discount_validation(logged_in_client):
    response = logged_in_client.post(
        reverse("ycms:product-create-upload"),
        _product_payload(isReduced="true", reducedPrice="59.90"),
    )

    assert response.status_code == 201
    assert Product.objects.count() == 1


@override_settings(LANGUAGES=(("de", "Deutsch"), ("en", "Englisch")))
def test_cms_product_detail_creates_language_variant(logged_in_client):
    product = _create_product(title="Deutsches Produkt")

    response = logged_in_client.get(
        reverse("ycms:product-detail", args=[product.id, product.slug]),
        HTTP_ACCEPT_LANGUAGE="en",
    )

    assert response.status_code == 200
    translation = Product.objects.get(original=product, language="en")
    assert translation.title == product.title
    assert translation.is_active is False
    # Kein Sprach-Suffix mehr im Slug (die Sprache steckt im URL-Pfad, /en/...).
    assert translation.slug
    assert not translation.slug.endswith("-en")


@override_settings(LANGUAGES=(("de", "Deutsch"), ("en", "Englisch")))
def test_public_product_search_uses_active_language_variant(client):
    """Sichert die Mehrsprachigkeit ab - greift erst, wenn Englisch in
    settings.LANGUAGES wieder aktiviert wird (aktuell läuft die Seite nur auf Deutsch)."""
    product = _create_product(title="Deutsches Produkt", description="Deutsche Beschreibung")
    translation = Product.objects.create(
        title="English Product",
        description="English description",
        price=product.price,
        weight=product.weight,
        is_active=True,
        is_in_stock=True,
        online_sell=True,
        language="en",
        original=product,
    )
    translation.categories.set(product.categories.all())

    response = client.get("/shop/products/search/", HTTP_ACCEPT_LANGUAGE="en")

    assert response.status_code == 200
    payload = response.json()
    assert payload["products"][0]["title"] == "English Product"
    assert payload["products"][0]["detail_url"].endswith(
        reverse("product-detail", args=[translation.id, translation.slug])
    )


def test_public_product_search_stays_german_for_english_browser(client):
    """Solange nur Deutsch in settings.LANGUAGES steht, bekommt auch ein englischer
    Browser die deutsche Variante - es gibt keine englische Seite mehr."""
    product = _create_product(title="Deutsches Produkt", description="Deutsche Beschreibung")
    translation = Product.objects.create(
        title="English Product",
        description="English description",
        price=product.price,
        weight=product.weight,
        is_active=True,
        is_in_stock=True,
        online_sell=True,
        language="en",
        original=product,
    )
    translation.categories.set(product.categories.all())

    response = client.get("/shop/products/search/", HTTP_ACCEPT_LANGUAGE="en-US,en;q=0.9")

    assert response.status_code == 200
    assert response.json()["products"][0]["title"] == "Deutsches Produkt"


def test_public_shop_map_locations_use_active_product_addresses(client):
    active = _create_product(
        title="Wohnung mit Adresse",
        address="Schillerstr. 6b, 94447 Plattling",
        showcase_only=True,
    )
    _create_product(
        title="Inaktive Wohnung",
        address="Musterstr. 1, 94447 Plattling",
        is_active=False,
        showcase_only=True,
    )
    _create_product(title="Wohnung ohne Adresse", address="", showcase_only=True)

    response = client.get(reverse("products"))
    html = response.content.decode()

    assert response.status_code == 200
    assert 'id="immobilien-karte"' in html
    assert response.context["product_map_locations"] == [
        {
            "id": active.id,
            "title": "Wohnung mit Adresse",
            "address": "Schillerstr. 6b, 94447 Plattling",
            "lat": None,
            "lng": None,
            "url": reverse(
                "product-detail",
                kwargs={"product_id": active.id, "slug": active.slug},
            ),
            "maps_url": active.maps_url,
        }
    ]
    assert "Schillerstr. 6b, 94447 Plattling" in html
    assert "Musterstr. 1, 94447 Plattling" not in html


@override_settings(GOOGLE_MAPS_JS_API_KEY="test-key")
def test_public_shop_map_hands_google_maps_the_stored_coordinates(client):
    """Die Karte bekommt fertige Koordinaten - im Browser wird nichts nachgeschlagen."""
    first = _create_product(
        title="Wohnung A",
        address="Schillerstr. 6b, 94447 Plattling",
        showcase_only=True,
    )
    second = _create_product(
        title="Wohnung B",
        address="Schillerstr. 6b, 94447 Plattling",
        showcase_only=True,
    )
    Product.objects.filter(pk__in=[first.pk, second.pk]).update(latitude=48.7772, longitude=12.8763)

    response = client.get(reverse("products"))
    html = response.content.decode()

    assert response.status_code == 200
    assert 'data-map-api-key="test-key"' in html
    # Dieselbe Anschrift an zwei Objekten ist erlaubt und ergibt zwei Marker.
    assert [
        (entry["title"], entry["lat"], entry["lng"])
        for entry in response.context["product_map_locations"]
    ] == [
        ("Wohnung A", 48.7772, 12.8763),
        ("Wohnung B", 48.7772, 12.8763),
    ]


def test_cms_product_form_saves_typed_address_and_locates_it(logged_in_client, monkeypatch):
    """Die Anschrift wird frei eingetippt, die Koordinaten kommen beim Speichern dazu."""
    lookups = []

    def fake_geocode(address):
        lookups.append(address)
        return 48.7772, 12.8763

    monkeypatch.setattr(
        "yoolink.ycms.applications.shop.geocoding.geocode_address", fake_geocode
    )

    first = logged_in_client.post(
        reverse("ycms:product-create-upload"),
        _product_payload(title="Wohnung A"),
    )
    assert first.status_code == 201

    product = Product.objects.get(title="Wohnung A")
    assert product.address == "Schillerstr. 6b, 94447 Plattling"
    assert (product.latitude, product.longitude) == (48.7772, 12.8763)

    second = logged_in_client.post(
        reverse("ycms:product-create-upload"),
        _product_payload(title="Wohnung B"),
    )
    assert second.status_code == 201

    twin = Product.objects.get(title="Wohnung B")
    assert (twin.latitude, twin.longitude) == (48.7772, 12.8763)
    # Eine bereits verortete Anschrift wird kein zweites Mal nachgeschlagen.
    assert lookups == ["Schillerstr. 6b, 94447 Plattling"]

    cleared = logged_in_client.post(
        reverse("ycms:product-detail-update", args=[product.id, product.slug]),
        _product_payload(title="Wohnung A", address=""),
    )
    assert cleared.status_code == 200

    product.refresh_from_db()
    assert product.address == ""
    assert product.latitude is None and product.longitude is None


def test_cms_pin_correction_sticks_and_moves_the_whole_house(logged_in_client, monkeypatch):
    """Ein im CMS verschobener Pin gilt fuer alle Objekte derselben Anschrift."""
    monkeypatch.setattr(
        "yoolink.ycms.applications.shop.geocoding.geocode_address", lambda address: (48.7772, 12.8763)
    )
    monkeypatch.setattr(
        "yoolink.ycms.applications.shop.views.geocode_address", lambda address: (48.7700, 12.8700)
    )

    for title in ("Wohnung A", "Wohnung B"):
        assert logged_in_client.post(
            reverse("ycms:product-create-upload"), _product_payload(title=title)
        ).status_code == 201
    first = Product.objects.get(title="Wohnung A")
    update_url = reverse("ycms:product-detail-update", args=[first.id, first.slug])

    moved = logged_in_client.post(
        update_url,
        _product_payload(title="Wohnung A", latitude="48.7781234", longitude="12.8755678", position_manual="true"),
    )
    assert moved.status_code == 200
    assert moved.json()["positionManual"] is True

    for product in Product.objects.filter(title__in=["Wohnung A", "Wohnung B"]):
        assert (product.latitude, product.longitude) == (48.7781234, 12.8755678)
        assert product.position_manual

    # Ein spaeteres Speichern ohne Kartenfelder laesst die Korrektur stehen.
    assert logged_in_client.post(update_url, _product_payload(title="Wohnung A")).status_code == 200
    first.refresh_from_db()
    assert (first.latitude, first.longitude, first.position_manual) == (48.7781234, 12.8755678, True)

    # Ungueltige Werte fallen auf die gespeicherte Position zurueck.
    logged_in_client.post(
        update_url, _product_payload(title="Wohnung A", latitude="abc", longitude="", position_manual="true")
    )
    first.refresh_from_db()
    assert (first.latitude, first.longitude) == (48.7781234, 12.8755678)

    # "Automatisch bestimmen" fragt den Geocoder neu - fuer das ganze Haus.
    reset = logged_in_client.post(update_url, _product_payload(title="Wohnung A", position_reset="true"))
    assert reset.json()["positionManual"] is False
    for product in Product.objects.filter(title__in=["Wohnung A", "Wohnung B"]):
        assert (product.latitude, product.longitude, product.position_manual) == (48.77, 12.87, False)


def test_title_image_alt_and_title_reach_the_public_pages(logged_in_client, client):
    product = _create_product(title="Goethestraße 3", showcase_only=True)
    update_url = reverse("ycms:product-detail-update", args=[product.id, product.slug])
    response = logged_in_client.post(
        update_url,
        _product_payload(
            title="Goethestraße 3",
            title_image_alt="Wohnanlage Goethestraße 3 von der Straße aus",
            title_image_title="Goethestraße 3",
        ),
    )
    assert response.status_code == 200

    product.refresh_from_db()
    assert product.title_image_alt == "Wohnanlage Goethestraße 3 von der Straße aus"
    assert product.title_image_alt_text == "Wohnanlage Goethestraße 3 von der Straße aus"

    product.title_image_alt = ""
    assert product.title_image_alt_text == "Goethestraße 3"


def test_objects_pdf_is_chosen_in_the_cms_and_embedded_on_the_products_page(logged_in_client, client):
    document = AnyFile.objects.create(
        file=SimpleUploadedFile("objekte.pdf", b"%PDF-1.4 test", content_type="application/pdf"),
        title="Unsere Objekte 2026",
    )
    response = logged_in_client.post(
        reverse("cms:shop-settings-update"),
        {
            "products_layout": "grouped",
            "products_title": "Immobilien",
            "products_intro": "",
            "objects_document_id": str(document.pk),
            "objects_document_title": "Unsere Objekte",
        },
    )
    assert response.status_code == 200
    assert ShopSettings.get_solo().objects_document == document

    page = client.get(reverse("products")).content.decode("utf-8")
    assert 'id="objektliste"' in page
    assert document.file.url in page

    logged_in_client.post(
        reverse("cms:shop-settings-update"),
        {"products_layout": "grouped", "products_title": "Immobilien", "objects_document_id": ""},
    )
    assert ShopSettings.get_solo().objects_document is None
    assert 'id="objektliste"' not in client.get(reverse("products")).content.decode("utf-8")


def test_public_product_detail_shows_file_display_name_not_storage_path(client):
    document = AnyFile.objects.create(
        title="Expose",
        file=SimpleUploadedFile("dokumente-und-downloads.pdf", b"%PDF-1.4", content_type="application/pdf"),
    )
    product = _create_product(title="Wohnung mit Datei", showcase_only=True)
    product.files.add(document)

    response = client.get(reverse("product-detail", kwargs={"product_id": product.id, "slug": product.slug}))
    html = response.content.decode()

    assert response.status_code == 200
    assert ">Expose.pdf<" in html


def test_public_product_detail_shows_address_once_and_links_to_inquiry(client):
    product = _create_product(
        title="Wohnung mit Adresse",
        address="Schillerstr. 6b, 94447 Plattling",
        showcase_only=True,
    )

    response = client.get(reverse("product-detail", kwargs={"product_id": product.id, "slug": product.slug}))
    html = response.content.decode()

    assert response.status_code == 200
    # Frueher stand die Anschrift zweimal auf der Seite: als Chip unter dem Titel
    # und noch einmal als Kachel neben dem Preis.
    assert html.count("Schillerstr. 6b, 94447 Plattling") == 1
    assert "bi bi-geo-alt" in html
    assert escape(product.maps_url) in html
    assert f'{reverse("kontakt")}?formular=allgemein&amp;immobilie={product.id}#kontaktformular' in html


def test_public_product_detail_breaks_pasted_nonbreaking_spaces(client):
    """Aus Word eingefuegter Text darf in der schmalen Spalte nicht mitten im Wort umbrechen."""
    product = _create_product(title="Wohnung mit Fliesstext", showcase_only=True)
    # Geschuetzte Leerzeichen als Escape: im Quelltext waeren sie nicht zu sehen.
    product.description = "<p>Diese\u00a0gepflegte\u00a0Immobilie\u00a0mit\u00a0attraktiver\u00a0Lage.</p>"
    product.save()

    response = client.get(reverse("product-detail", kwargs={"product_id": product.id, "slug": product.slug}))
    html = response.content.decode()
    description = re.search(r'<div class="rich-text.*?</div>', html, re.S).group(0)

    assert response.status_code == 200
    assert "Diese gepflegte Immobilie mit attraktiver Lage." in description
    assert "\u00a0" not in description
    assert "&nbsp;" not in description


def test_public_product_search_filters_by_regular_price():
    _create_product(title="Teuer", price=Decimal("100.00"))
    _create_product(
        title="Guenstig",
        price=Decimal("25.00"),
    )

    response = APIClient().get(
        "/shop/products/search/",
        {"max_price": "30", "ordering": "price_asc"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["pagination"]["total_count"] == 1
    assert payload["products"][0]["title"] == "Guenstig"
    assert payload["products"][0]["effective_price"] == "25.00"


def test_cart_checkout_and_admin_status_mail_flow(client, logged_in_client, cms_user):
    product = _create_product(price=Decimal("20.00"), weight=Decimal("1.0000"))

    add_response = client.post(
        f"/shop/api/cart/add/{product.id}/",
        data={"amount": "2"},
    )
    assert add_response.status_code == 200
    order_id = add_response.json()["order_id"]

    cart_response = client.get("/shop/api/cart/")
    assert cart_response.status_code == 200
    assert cart_response.json()["cart_amount"] == 1
    assert cart_response.json()["total_price"] == 45.49

    verify_cart_response = client.post(
        "/shop/api/cart/verify/",
        data={"buyer_email": "buyer@example.com", "buyer_name": "Buyer"},
    )
    assert verify_cart_response.status_code == 200
    assert len(mail.outbox) == 1

    order = Order.objects.get(id=order_id)
    assert order.buyer_email == "buyer@example.com"
    assert order.verified is False

    verify_order_response = client.post(
        "/shop/api/order/verify/",
        data={
            "order_id": order.id,
            "token": str(order.uuid),
            "buyer_prename": "Buyer",
            "buyer_name": "Person",
            "address": "Teststrasse 1",
            "city": "Berlin",
            "postal_code": "10115",
            "country": "Deutschland",
            "shipping": Order.ShippingMethod.PICKUP,
            "payment": Order.PaymentMethod.CASH,
        },
    )
    assert verify_order_response.status_code == 200
    order.refresh_from_db()
    assert order.verified is True
    assert Notification.objects.filter(order=order).exists()

    status_response = logged_in_client.patch(
        reverse("ycms:update_order_status", args=[order.id]),
        data=json.dumps({"status": Order.Status.PAID}),
        content_type="application/json",
    )
    assert status_response.status_code == 200
    order.refresh_from_db()
    assert order.status == Order.Status.PAID
    assert order.paid is True
    assert len(mail.outbox) >= 3


def test_grouped_overview_ships_the_data_the_client_side_filter_needs(client):
    """Die gruppierte Uebersicht filtert im Browser - dafuer muessen die Karten die
    passenden data-Attribute mitbringen (siehe pages/shop_grouped.html)."""
    settings_obj = ShopSettings.get_solo()
    settings_obj.products_layout = ShopSettings.ProductsLayout.GROUPED
    settings_obj.save(update_fields=["products_layout"])

    group = ProductGroup.objects.create(name="Wohnungen", slug="wohnungen", sort_order=1)
    with_price = Product.objects.create(
        title="Drei-Zimmer-Wohnung",
        slug="drei-zimmer",
        is_active=True,
        price=Decimal("750.00"),
        group=group,
        description="Hell und ruhig.",
    )

    # Objekt ohne sichtbaren Preis: darf bei gesetztem Preisbereich nicht mitzaehlen.
    Product.objects.create(
        title="Garage",
        slug="garage",
        is_active=True,
        price=Decimal("60.00"),
        showcase_only=True,
        show_price_when_showcase=False,
        description="Einzelgarage.",
    )

    response = client.get(reverse("products"))
    html = response.content.decode()

    assert response.status_code == 200
    assert response.context["filter_categories"] == []

    assert 'id="groupedSearchInput"' in html
    assert "data-filter-category" not in html
    assert 'id="groupedMinPrice"' in html
    assert 'id="groupedNoResults"' in html
    # Zaehler, die das Skript live nachfuehrt
    assert 'data-group-count="all"' in html
    assert 'data-group-count="gruppe-wohnungen"' in html
    assert 'data-group-count="gruppe-weitere"' in html
    assert "data-section-count" in html
    assert "data-product-link=" in html

    # Preis unlokalisiert - mit "750,00" wuerde parseFloat im Browser NaN liefern.
    assert 'data-price="750.00"' in html
    assert 'data-price=""' in html
    assert "data-categories=" not in html


def test_grouped_overview_filter_bar_is_collapsible(client):
    """Der Filterblock startet zugeklappt; aufgeklappt wird per Button (und vom
    Skript, sobald der Screen breit genug ist oder ein Filter gesetzt ist)."""
    settings_obj = ShopSettings.get_solo()
    settings_obj.products_layout = ShopSettings.ProductsLayout.GROUPED
    settings_obj.save(update_fields=["products_layout"])

    Product.objects.create(
        title="Drei-Zimmer-Wohnung",
        slug="drei-zimmer-toggle",
        is_active=True,
        price=Decimal("750.00"),
    )

    html = client.get(reverse("products")).content.decode()

    assert 'id="groupedToggleFilters"' in html
    assert 'aria-controls="groupedFilterBody"' in html
    assert 'aria-expanded="false"' in html
    assert 'id="groupedActiveFilterCount"' in html
    # Der Block traegt "hidden" statt "grid" - das Skript tauscht beim Aufklappen.
    assert 'id="groupedFilterBody" class="mt-4 hidden grid-cols-1' in html
    # Die Suche bleibt immer sichtbar, sie darf nicht im Klappblock stecken.
    assert html.index('id="groupedSearchInput"') < html.index('id="groupedFilterBody"')
