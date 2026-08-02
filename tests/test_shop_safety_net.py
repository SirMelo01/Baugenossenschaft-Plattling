import json
from decimal import Decimal

import pytest
from django.core import mail
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from yoolink.users.tests.factories import UserFactory
from yoolink.ycms.applications.shop.models import (
    Brand,
    Category,
    Order,
    OrderItem,
    Product,
    ProductSpecification,
    ShippingAddress,
)
from yoolink.ycms.applications.notifications.models import Notification
from yoolink.ycms.models import UserSettings

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
        "hersteller": "YooLink",
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
    brand, _ = Brand.objects.get_or_create(name=overrides.pop("brand_name", "YooLink"))
    category, _ = Category.objects.get_or_create(name=overrides.pop("category_name", "CMS"))
    product = Product.objects.create(
        title=overrides.pop("title", "Test Produkt"),
        description=overrides.pop("description", "Beschreibung"),
        price=overrides.pop("price", Decimal("49.90")),
        weight=overrides.pop("weight", Decimal("1.5000")),
        brand=brand,
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
    assert product.effective_price == Decimal("39.90")
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
    assert product.brand.name == "YooLink"
    assert set(product.categories.values_list("name", flat=True)) == {"CMS", "Hosting"}
    assert list(ProductSpecification.objects.values_list("key", "value")) == [
        ("Material", "Code"),
        ("Version", "1.0"),
    ]

    search_response = logged_in_client.get(
        reverse("ycms:product_search"),
        {"q": "Produkt", "availability": "online"},
    )
    assert search_response.status_code == 200
    assert search_response.json()["pagination"]["total_count"] == 1

    update_response = logged_in_client.post(
        reverse("ycms:product-detail-update", args=[product.id, product.slug]),
        _product_payload(title="Geändertes Produkt", isReduced="true", reducedPrice="39.90"),
    )
    assert update_response.status_code == 200
    product.refresh_from_db()
    assert product.title == "Geändertes Produkt"
    assert product.discount_price == Decimal("39.90")

    delete_response = logged_in_client.post(
        reverse("ycms:product-detail-delete", args=[product.id, product.slug])
    )
    assert delete_response.status_code == 200
    assert Product.objects.count() == 0


def test_cms_product_create_saves_discount_price(logged_in_client):
    response = logged_in_client.post(
        reverse("ycms:product-create-upload"),
        _product_payload(isReduced="true", reducedPrice="39.90"),
    )

    assert response.status_code == 201
    product = Product.objects.get()
    assert product.is_reduced is True
    assert product.discount_price == Decimal("39.90")


def test_cms_product_create_ignores_reduced_price_when_switch_is_off(logged_in_client):
    response = logged_in_client.post(
        reverse("ycms:product-create-upload"),
        _product_payload(reducedPrice="39.90"),
    )

    assert response.status_code == 201
    product = Product.objects.get()
    assert product.is_reduced is False
    assert product.discount_price is None


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


def test_cms_product_create_returns_discount_validation_message(logged_in_client):
    response = logged_in_client.post(
        reverse("ycms:product-create-upload"),
        _product_payload(isReduced="true", reducedPrice="59.90"),
    )

    assert response.status_code == 400
    assert response.json()["error"] == "Der reduzierte Preis muss kleiner als der Normalpreis sein."
    assert Product.objects.count() == 0


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


def test_public_product_search_uses_active_language_variant(client):
    product = _create_product(title="Deutsches Produkt", description="Deutsche Beschreibung")
    translation = Product.objects.create(
        title="English Product",
        description="English description",
        price=product.price,
        weight=product.weight,
        brand=product.brand,
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


def test_public_product_search_filters_by_effective_price():
    _create_product(title="Teuer", price=Decimal("100.00"))
    _create_product(
        title="Reduziert",
        price=Decimal("80.00"),
        is_reduced=True,
        discount_price=Decimal("25.00"),
    )

    response = APIClient().get(
        "/shop/products/search/",
        {"max_price": "30", "ordering": "price_asc"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["pagination"]["total_count"] == 1
    assert payload["products"][0]["title"] == "Reduziert"
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
