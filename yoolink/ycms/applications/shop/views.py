import json
from datetime import timedelta
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Case, Count, DecimalField, ExpressionWrapper, F, Max, Sum, When
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import get_language, get_language_from_request
from rest_framework import status
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema
from django.core.paginator import Paginator
from django.db.models import Q

from django.utils.html import strip_tags

from yoolink.utils.sanitize_html import sanitize_html
from yoolink.views import get_opening_hours
from yoolink.ycms.models import AnyFile, Galerie, UserSettings, fileentry
from yoolink.ycms.upload_validation import validate_image_upload
from yoolink.ycms.views import (
    DESKTOP_IMAGE_MAX_DIMENSIONS,
    DESKTOP_IMAGE_TARGET_KB,
    compress_image,
    optimize_image_for_upload,
    resize_image,
    scale_image,
)

from .serializers import OrderItemSerializer, OrderSerializer
from ...views import send_mail
from .models import (
    Brand,
    Category,
    Order,
    OrderItem,
    Product,
    ProductGroup,
    ProductSpecification,
    Review,
    ShippingAddress,
    ShopSettings,
)
from .mail_service import (
    send_payment_confirmation,
    send_ready_for_pickup_confirmation,
    send_shipping_confirmation,
)

# =========================================================
# General helpers
# =========================================================

def parse_bool(value):
    """Convert common truthy string values to bool."""
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def parse_decimal(value, default="0.00"):
    """Parse a decimal value safely from request input."""
    try:
        return Decimal(str(value or default).replace(",", "."))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal(default)


def parse_json_list(value):
    """Parse a JSON encoded list safely."""
    if not value:
        return []
    try:
        data = json.loads(value)
        return data if isinstance(data, list) else []
    except json.JSONDecodeError:
        return []


def validation_error_to_message(error):
    """Return the first readable message from a Django ValidationError."""
    if hasattr(error, "message_dict"):
        for messages in error.message_dict.values():
            if isinstance(messages, (list, tuple)) and messages:
                return str(messages[0])
            if messages:
                return str(messages)

    if getattr(error, "messages", None):
        return str(error.messages[0])

    return str(error)


def get_active_product_language(request):
    lang = get_language_from_request(request) or getattr(request, "LANGUAGE_CODE", None) or get_language() or settings.LANGUAGE_CODE
    available_languages = dict(settings.LANGUAGES)
    return lang if lang in available_languages else settings.LANGUAGE_CODE


def get_product_root(product):
    return product.original if product.original_id else product


def clone_product_translation(original_product, language):
    product = Product.objects.create(
        title=original_product.title,
        description=original_product.description,
        sku=original_product.sku,
        price_note=original_product.price_note,
        featured=original_product.featured,
        price=original_product.price,
        discount_price=original_product.discount_price,
        title_image=original_product.title_image,
        gallery=original_product.gallery,
        is_reduced=original_product.is_reduced,
        is_active=False,
        is_in_stock=original_product.is_in_stock,
        online_sell=original_product.online_sell,
        showcase_only=original_product.showcase_only,
        show_price_when_showcase=original_product.show_price_when_showcase,
        brand=original_product.brand,
        group=original_product.group,
        weight=original_product.weight,
        language=language,
        original=original_product,
    )
    product.categories.set(original_product.categories.all())
    product.files.set(original_product.files.all())
    ProductSpecification.objects.bulk_create(
        [
            ProductSpecification(
                product=product,
                key=spec.key,
                value=spec.value,
                sort_order=spec.sort_order,
            )
            for spec in original_product.specifications.all()
        ]
    )
    return product


def get_or_create_product_translation(product, language):
    original_product = get_product_root(product)

    if original_product.language == language:
        return original_product

    translation = original_product.translations.filter(language=language).first()
    if translation:
        return translation

    return clone_product_translation(original_product, language)


def get_localized_product(product, language, require_active=False):
    root = get_product_root(product)

    if root.language == language and (root.is_active or not require_active):
        return root

    variants = root.translations.all()
    for variant in variants:
        if variant.language == language and (variant.is_active or not require_active):
            return variant

    return root


def get_public_user_settings():
    """Return the public company profile used for shop mails."""
    return UserSettings.objects.filter(user__is_staff=False).first()


def get_image_url(image_field):
    """Return a safe image URL string."""
    try:
        return image_field.url if image_field else ""
    except Exception:
        return ""


def build_contact_signature(user_settings):
    """Build the mail signature block from user settings."""
    if not user_settings:
        return "\n\nUnterstützt durch YooLink\nhttps://yoolink.de"

    lines = [f"\n\nMit freundlichen Grüßen,\n{user_settings.full_name}"]

    if user_settings.company_name:
        lines.append(user_settings.company_name)

    if user_settings.tel_number and user_settings.tel_number != "0":
        lines.append(f"Tel. {user_settings.tel_number}")

    if user_settings.fax_number and user_settings.fax_number != "0":
        lines.append(f"Fax {user_settings.fax_number}")

    if user_settings.mobile_number and user_settings.mobile_number != "0":
        lines.append(f"Handy {user_settings.mobile_number}")

    if user_settings.website:
        lines.append(user_settings.website)

    lines.append("")
    lines.append("Unterstützt durch YooLink")
    lines.append("https://yoolink.de")

    return "\n".join(lines)


def build_order_summary(order):
    """Build a reusable order summary for mails."""
    lines = []

    for item in order.items.select_related("product").all():
        lines.append(f"{item.quantity}x {item.product.title} - {item.subtotal():.2f} Euro")

    lines.append("------------------------------------------")
    lines.append(f"Nettopreis: {order.total_with_tax():.2f} Euro")
    lines.append(f"Lieferung: {order.shipping_price():.2f} Euro")
    lines.append(f"Umsatzsteuer (19%): {order.calculate_tax():.2f} Euro")
    lines.append("------------------------------------------")
    lines.append(f"Gesamtpreis: {order.total():.2f} Euro")

    return "\n".join(lines)


def process_product_image(uploaded_file):
    """Resize, scale and compress an uploaded product image."""
    if not uploaded_file:
        return None

    resized_image = resize_image(uploaded_file)
    scaled_image = scale_image(resized_image)
    return compress_image(scaled_image)


def get_or_create_brand(brand_name):
    """Create or return an existing brand."""
    if not brand_name:
        return None

    brand, _ = Brand.objects.get_or_create(
        name=brand_name.strip(),
        defaults={"website": ""},
    )
    return brand


def get_or_create_group(group_name):
    """Create or return an existing product group."""
    group_name = (group_name or "").strip()
    if not group_name:
        return None

    group = ProductGroup.objects.filter(name__iexact=group_name).first()
    if group:
        return group

    max_sort = ProductGroup.objects.aggregate(max_sort=Max("sort_order"))["max_sort"]
    return ProductGroup.objects.create(name=group_name, sort_order=(max_sort or 0) + 1)


def get_or_create_categories(category_names):
    """Create or return category instances from a list of names."""
    categories = []
    for category_name in category_names:
        cleaned_name = str(category_name).strip()
        if not cleaned_name:
            continue
        category, _ = Category.objects.get_or_create(name=cleaned_name)
        categories.append(category)
    return categories


from django.urls import reverse


def description_plain_text(product, max_length=None):
    """Return the description as condensed plain text (for cards/previews)."""
    # Pad tags with spaces so block boundaries don't glue words together.
    text = " ".join(strip_tags((product.description or "").replace("<", " <")).split())
    if max_length and len(text) > max_length:
        text = text[: max_length - 1].rstrip() + "…"
    return text


def serialize_product_for_search(product):
    translations = [
        {
            "language": translation.language,
            "is_active": translation.is_active,
            "detail_url": reverse(
                "cms:product-detail",
                kwargs={"product_id": translation.id, "slug": translation.slug},
            ),
        }
        for translation in product.translations.all()
    ]

    return {
        "id": product.id,
        "slug": product.slug,
        "title": product.title,
        "description": description_plain_text(product),
        "sku": product.sku or "",
        "price_note": product.price_note or "",
        "featured": product.featured,
        "price": str(product.price) if product.price is not None else "",
        "discount_price": str(product.discount_price) if product.discount_price is not None else "",
        "image_url": product.title_image.url if product.title_image else "",
        "detail_url": reverse(
            "cms:product-detail",
            kwargs={"product_id": product.id, "slug": product.slug},
        ),
        "is_active": product.is_active,
        "is_in_stock": product.is_in_stock,
        "online_sell": product.online_sell,
        "is_reduced": product.is_reduced,
        "showcase_only": getattr(product, "showcase_only", False),
        "show_price_when_showcase": getattr(product, "show_price_when_showcase", True),
        "brand": product.brand.name if product.brand else "",
        "group": product.group.name if product.group else "",
        "categories": [category.name for category in product.categories.all()],
        "language": product.language,
        "translations": translations,
        "updated_at": product.updated_at.strftime("%d.%m.%Y") if product.updated_at else "",
    }

def serialize_public_product(product):
    effective_price = getattr(product, "effective_price_value", None)
    if effective_price is None:
        effective_price = product.discount_price if product.is_reduced and product.discount_price else product.price

    return {
        "id": product.id,
        "slug": product.slug,
        "title": product.title,
        "description": description_plain_text(product, max_length=140),
        "price_note": product.price_note or "",
        "featured": product.featured,
        "image_url": product.title_image.url if product.title_image else "",
        "price": str(product.price) if product.price is not None else "",
        "discount_price": str(product.discount_price) if product.discount_price is not None else "",
        "effective_price": str(effective_price) if effective_price is not None else "",
        "showcase_only": getattr(product, "showcase_only", False),
        "show_price_when_showcase": getattr(product, "show_price_when_showcase", True),
        "is_in_stock": product.is_in_stock,
        "online_sell": product.online_sell,
        "is_reduced": product.is_reduced,
        "brand": product.brand.name if product.brand else "",
        "categories": [category.name for category in product.categories.all()],
        "detail_url": reverse(
            "product-detail",
            kwargs={"product_id": product.id, "slug": product.slug},
        ),
    }

def build_cart_items_payload(order):
    """Serialize cart items for frontend responses."""
    return [
        {
            "order_item_id": item.id,
            "product_title": item.product.title,
            "quantity": item.quantity,
            "price": float(item.get_price()),
            "subtotal": float(item.subtotal()),
        }
        for item in order.items.select_related("product").all()
    ]


def reset_cart_session(request):
    """Clear current cart session keys."""
    request.session["order_id"] = None
    request.session["cart_amount"] = 0
    request.session["cart_total_price"] = 0


def get_session_order(request):
    """Return the current session order or None."""
    order_id = request.session.get("order_id")
    if not order_id:
        return None

    try:
        return Order.objects.get(id=order_id)
    except Order.DoesNotExist:
        reset_cart_session(request)
        return None

def get_or_create_active_cart_order(request):
    """Return a valid open cart order for the current session."""
    order = get_session_order(request)

    if order and not order.verified and order.status == "OPEN":
        return order

    if order and (order.verified or order.status != "OPEN"):
        reset_cart_session(request)

    new_order = Order.objects.create(buyer_email="")
    request.session["order_id"] = new_order.id
    request.session.setdefault("cart_amount", 0)
    return new_order


def get_last_url(request):
    """Return the previous URL or fallback to root."""
    return request.META.get("HTTP_REFERER") or "/"


def build_order_line_total_expression():
    """Build a reusable ORM expression for effective line totals."""
    effective_price = Case(
        When(is_discounted=True, discounted_price__isnull=False, then=F("discounted_price")),
        default=F("unit_price"),
        output_field=DecimalField(max_digits=10, decimal_places=2),
    )
    return ExpressionWrapper(
        F("quantity") * effective_price,
        output_field=DecimalField(max_digits=12, decimal_places=2),
    )

def parse_product_specifications(raw_value):
    if not raw_value:
        return [], None

    try:
        payload = json.loads(raw_value)
    except (TypeError, ValueError):
        return None, "Die Spezifikationen konnten nicht verarbeitet werden."

    if not isinstance(payload, list):
        return None, "Ungültiges Format für Spezifikationen."

    parsed_specs = []
    seen_keys = set()

    for index, item in enumerate(payload):
        if not isinstance(item, dict):
            return None, "Ungültiger Spezifikationseintrag."

        key = str(item.get("key") or "").strip()
        value = str(item.get("value") or "").strip()
        sort_order = item.get("sort_order", index)

        if not key and not value:
            continue

        if not key or not value:
            return None, "Jede Spezifikation braucht eine Bezeichnung und einen Wert."

        normalized_key = key.lower()
        if normalized_key in seen_keys:
            return None, f'Die Spezifikation "{key}" wurde mehrfach eingetragen.'

        seen_keys.add(normalized_key)

        parsed_specs.append(
            {
                "key": key[:120],
                "value": value[:255],
                "sort_order": int(sort_order) if str(sort_order).isdigit() else index,
            }
        )

    return parsed_specs, None

def apply_product_form_data(request, product):
    """
    Apply validated request data to a product instance.

    Returns
    product, error_response
    """
    title = (request.POST.get("title") or "").strip()
    description = sanitize_html((request.POST.get("description") or "").strip())
    sku = (request.POST.get("sku") or "").strip()[:64]
    price_note = (request.POST.get("priceNote") or "").strip()[:120]
    brand_name = (request.POST.get("hersteller") or "").strip()
    group_name = (request.POST.get("group") or "").strip()
    selected_categories = parse_json_list(request.POST.get("selected_categories"))
    selected_file_ids = parse_json_list(request.POST.get("selected_file_ids"))
    specifications_payload = request.POST.get("specifications")
    gallery_id = request.POST.get("galeryId")
    uploaded_image = request.FILES.get("title_image")

    price = parse_decimal(request.POST.get("price"), default="0.00")
    weight = parse_decimal(request.POST.get("weight"), default="0.00")
    reduced_price_raw = (request.POST.get("reducedPrice") or "").strip()
    reduced_price = parse_decimal(reduced_price_raw, default="0.00") if reduced_price_raw else None

    is_active = parse_bool(request.POST.get("isActive"))
    is_in_stock = parse_bool(request.POST.get("isInStock"))
    online_sell = parse_bool(request.POST.get("isOnlineAvailable"))
    is_reduced = parse_bool(request.POST.get("isReduced"))
    showcase_only = parse_bool(request.POST.get("isShowcaseOnly"))
    show_price_when_showcase = parse_bool(request.POST.get("showPriceWhenShowcase"))
    featured = parse_bool(request.POST.get("isFeatured"))

    if not title:
        return None, JsonResponse({"error": "Der Titel darf nicht leer sein."}, status=400)

    if price <= 0:
        return None, JsonResponse({"error": "Der Preis muss größer 0 sein."}, status=400)

    if is_reduced and reduced_price is None:
        return None, JsonResponse({"error": "Ein reduzierter Artikel braucht einen Rabattpreis."}, status=400)

    if is_reduced and reduced_price <= 0:
        return None, JsonResponse({"error": "Der reduzierte Preis muss größer 0 sein."}, status=400)

    if is_reduced and reduced_price >= price:
        return None, JsonResponse({"error": "Der reduzierte Preis muss kleiner als der Normalpreis sein."}, status=400)

    if uploaded_image:
        try:
            validate_image_upload(uploaded_image)
        except ValidationError as error:
            return None, JsonResponse({"error": validation_error_to_message(error)}, status=400)

    duplicate_qs = Product.objects.filter(title=title, language=product.language)
    if product.pk:
        duplicate_qs = duplicate_qs.exclude(pk=product.pk)

    if duplicate_qs.exists():
        return None, JsonResponse({"error": "Ein Produkt mit diesem Titel existiert bereits."}, status=400)

    gallery_instance = None
    if gallery_id:
        gallery_instance = get_object_or_404(Galerie, id=int(gallery_id))

    selected_files = AnyFile.objects.filter(id__in=selected_file_ids)

    parsed_specifications, specifications_error = parse_product_specifications(specifications_payload)
    if specifications_error:
        return None, JsonResponse({"error": specifications_error}, status=400)

    try:
        with transaction.atomic():
            product.title = title
            product.description = description
            product.sku = sku
            product.price_note = price_note
            product.featured = featured
            product.price = price
            product.weight = weight
            product.discount_price = reduced_price if is_reduced else None
            product.is_active = is_active
            product.is_in_stock = is_in_stock
            product.online_sell = online_sell
            product.is_reduced = is_reduced
            product.showcase_only = showcase_only
            product.show_price_when_showcase = show_price_when_showcase
            product.brand = get_or_create_brand(brand_name)
            product.group = get_or_create_group(group_name)

            if gallery_instance:
                product.gallery = gallery_instance

            product.save()

            product.categories.clear()
            for category in get_or_create_categories(selected_categories):
                product.categories.add(category)

            product.files.set(selected_files)

            product.specifications.all().delete()
            ProductSpecification.objects.bulk_create(
                [
                    ProductSpecification(
                        product=product,
                        key=spec["key"],
                        value=spec["value"],
                        sort_order=spec["sort_order"],
                    )
                    for spec in parsed_specifications
                ]
            )

            processed_image = process_product_image(uploaded_image)
            if processed_image:
                product.title_image = processed_image
                product.save()
    except ValidationError as error:
        return None, JsonResponse({"error": validation_error_to_message(error)}, status=400)

    return product, None


# =========================================================
# CMS product views
# =========================================================

@login_required(login_url="login")
def product_view(request):
    """Render the CMS product overview."""
    queryset = get_filtered_products_queryset(request)
    paginator = Paginator(queryset, 9)
    page_obj = paginator.get_page(request.GET.get("page", 1))

    context = {
        "page_obj": page_obj,
        "filters": {
            "q": request.GET.get("q", ""),
            "status": request.GET.get("status", ""),
            "availability": request.GET.get("availability", ""),
            "type": request.GET.get("type", ""),
            "ordering": request.GET.get("ordering", "title_asc"),
        },
    }
    return render(request, "pages/cms/products/overview.html", context)


@login_required(login_url="login")
def product_create_view(request):
    """Render the CMS product create page."""
    return render(request, "pages/cms/products/create-product.html", {})


@login_required(login_url="login")
def product_detail(request, product_id, slug):
    """Render the CMS product edit page."""
    product = get_object_or_404(
        Product.objects.select_related("brand", "gallery", "original", "group")
        .prefetch_related("categories", "files", "specifications", "translations"),
        id=product_id,
        slug=slug,
    )
    product = get_or_create_product_translation(product, get_active_product_language(request))
    return render(request, "pages/cms/products/edit-product.html", {"product": product})

def get_filtered_products_queryset(request):
    query = (request.GET.get("q") or "").strip()
    status = (request.GET.get("status") or "").strip()
    availability = (request.GET.get("availability") or "").strip()
    product_type = (request.GET.get("type") or "").strip()
    ordering = (request.GET.get("ordering") or "title_asc").strip()

    products = (
        Product.objects.select_related("brand", "gallery")
        .prefetch_related("categories", "translations")
        .filter(original__isnull=True)
    )

    if query:
        products = products.filter(
            Q(title__icontains=query)
            | Q(description__icontains=query)
            | Q(brand__name__icontains=query)
            | Q(categories__name__icontains=query)
        ).distinct()

    if status == "active":
        products = products.filter(is_active=True)
    elif status == "inactive":
        products = products.filter(is_active=False)

    if availability == "in_stock":
        products = products.filter(is_in_stock=True)
    elif availability == "out_of_stock":
        products = products.filter(is_in_stock=False)
    elif availability == "online":
        products = products.filter(online_sell=True)
    elif availability == "offline":
        products = products.filter(online_sell=False)

    if product_type == "shop":
        products = products.filter(showcase_only=False)
    elif product_type == "showcase":
        products = products.filter(showcase_only=True)
    elif product_type == "reduced":
        products = products.filter(is_reduced=True)
    elif product_type == "with_price":
        products = products.filter(
            Q(showcase_only=False)
            | Q(showcase_only=True, show_price_when_showcase=True)
        )
    elif product_type == "without_price":
        products = products.filter(showcase_only=True, show_price_when_showcase=False)

    ordering_map = {
        "title_asc": "title",
        "title_desc": "-title",
        "updated_desc": "-updated_at",
        "updated_asc": "updated_at",
        "created_desc": "-created_at",
        "created_asc": "created_at",
        "price_asc": "price",
        "price_desc": "-price",
    }

    return products.order_by(ordering_map.get(ordering, "title"))


@login_required(login_url="login")
def product_search(request):
    """Search products for CMS usage."""
    queryset = get_filtered_products_queryset(request)
    paginator = Paginator(queryset, 9)
    page_obj = paginator.get_page(request.GET.get("page", 1))

    data = [serialize_product_for_search(product) for product in page_obj.object_list]

    return JsonResponse(
        {
            "products": data,
            "pagination": {
                "current_page": page_obj.number,
                "num_pages": paginator.num_pages,
                "has_previous": page_obj.has_previous(),
                "has_next": page_obj.has_next(),
                "previous_page_number": page_obj.previous_page_number() if page_obj.has_previous() else None,
                "next_page_number": page_obj.next_page_number() if page_obj.has_next() else None,
                "total_count": paginator.count,
                "page_size": paginator.per_page,
            },
        }
    )

@login_required(login_url="login")
def product_create(request):
    """Create a new product from CMS form data."""
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request method. Only POST requests are allowed."}, status=405)

    product = Product()
    product.language = get_active_product_language(request)
    product, error_response = apply_product_form_data(request, product)

    if error_response:
        return error_response

    return JsonResponse(
        {
            "success": "Product successfully created",
            "productId": product.id,
            "slug": product.slug,
        },
        status=201,
    )


@login_required(login_url="login")
def product_update(request, product_id, slug):
    """Update an existing product from CMS form data."""
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request method. Only POST requests are allowed."}, status=405)

    product = get_object_or_404(Product, id=product_id, slug=slug)
    product = get_or_create_product_translation(product, get_active_product_language(request))
    product, error_response = apply_product_form_data(request, product)

    if error_response:
        return error_response

    return JsonResponse(
        {
            "success": "Product successfully updated",
            "productId": product.id,
            "slug": product.slug,
        },
        status=200,
    )


@login_required(login_url="login")
def shop_settings_update(request):
    """Update the public product page settings from the CMS."""
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request method. Only POST requests are allowed."}, status=405)

    shop_settings = ShopSettings.get_solo()

    layout = (request.POST.get("products_layout") or "").strip()
    valid_layouts = {choice[0] for choice in ShopSettings.ProductsLayout.choices}
    if layout not in valid_layouts:
        return JsonResponse({"error": "Ungültiges Layout."}, status=400)

    products_title = (request.POST.get("products_title") or "").strip()[:120]
    products_intro = (request.POST.get("products_intro") or "").strip()[:1000]

    shop_settings.products_layout = layout
    shop_settings.products_title = products_title or "Produkte"
    shop_settings.products_intro = products_intro
    shop_settings.save()

    return JsonResponse({"success": "Die Shop Einstellungen wurden gespeichert."})


@login_required(login_url="login")
def product_description_image_upload(request):
    """Upload an inline image for the rich text product description."""
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request method. Only POST requests are allowed."}, status=405)

    uploaded_file = request.FILES.get("image") or request.FILES.get("file")
    if not uploaded_file:
        return JsonResponse({"error": "Keine Datei übermittelt."}, status=400)

    try:
        validate_image_upload(uploaded_file)
    except ValidationError as error:
        return JsonResponse({"error": validation_error_to_message(error)}, status=400)

    optimized_image = optimize_image_for_upload(
        uploaded_file,
        max_dimensions=DESKTOP_IMAGE_MAX_DIMENSIONS,
        max_size_kb=DESKTOP_IMAGE_TARGET_KB,
        variant_suffix="desktop",
    )

    image = fileentry.objects.create(
        file=optimized_image,
        title=getattr(uploaded_file, "name", "Produktbild"),
    )

    return JsonResponse({"success": "Bild erfolgreich hochgeladen.", "url": image.file.url})


@login_required(login_url="login")
def get_categories(request):
    """Return all categories (with product counts) for the CMS picker."""
    categories = Category.objects.annotate(product_count=Count("products", distinct=True)).order_by("name")
    return JsonResponse(
        {
            "categories": [category.name for category in categories],
            "items": [
                {"id": category.id, "name": category.name, "product_count": category.product_count}
                for category in categories
            ],
        }
    )


@login_required(login_url="login")
def get_brands(request):
    """Return all brands (with product counts) for the CMS picker."""
    brands = Brand.objects.annotate(product_count=Count("products", distinct=True)).order_by("name")
    return JsonResponse(
        {
            "brands": [brand.name for brand in brands],
            "items": [
                {"id": brand.id, "name": brand.name, "product_count": brand.product_count}
                for brand in brands
            ],
        }
    )


@login_required(login_url="login")
def get_groups(request):
    """Return all product groups (with counts) ordered for the CMS picker."""
    groups = ProductGroup.objects.annotate(product_count=Count("products", distinct=True)).order_by("sort_order", "name")
    return JsonResponse(
        {
            "groups": [group.name for group in groups],
            "items": [
                {
                    "id": group.id,
                    "name": group.name,
                    "sort_order": group.sort_order,
                    "product_count": group.product_count,
                }
                for group in groups
            ],
        }
    )


@login_required(login_url="login")
def group_create(request):
    """Create a new product group from the CMS picker."""
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request method. Only POST requests are allowed."}, status=405)

    name = (request.POST.get("name") or "").strip()[:255]
    if not name:
        return JsonResponse({"error": "Der Name der Gruppe darf nicht leer sein."}, status=400)

    if ProductGroup.objects.filter(name__iexact=name).exists():
        return JsonResponse({"error": "Eine Gruppe mit diesem Namen existiert bereits."}, status=400)

    group = get_or_create_group(name)
    return JsonResponse({"success": "Gruppe wurde erstellt.", "id": group.id, "name": group.name}, status=201)


@login_required(login_url="login")
def group_move(request, group_id):
    """Move a product group up or down in the public section order."""
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request method. Only POST requests are allowed."}, status=405)

    direction = (request.POST.get("direction") or "").strip()
    if direction not in {"up", "down"}:
        return JsonResponse({"error": "Ungültige Richtung."}, status=400)

    groups = list(ProductGroup.objects.order_by("sort_order", "name"))
    index = next((i for i, group in enumerate(groups) if group.id == group_id), None)
    if index is None:
        return JsonResponse({"error": "Gruppe wurde nicht gefunden."}, status=404)

    swap_index = index - 1 if direction == "up" else index + 1
    if swap_index < 0 or swap_index >= len(groups):
        return JsonResponse({"success": "Reihenfolge unverändert."})

    groups[index], groups[swap_index] = groups[swap_index], groups[index]

    with transaction.atomic():
        for position, group in enumerate(groups):
            if group.sort_order != position:
                ProductGroup.objects.filter(pk=group.pk).update(sort_order=position)

    return JsonResponse({"success": "Reihenfolge wurde angepasst."})


@login_required(login_url="login")
def group_delete(request, group_id):
    """Delete a product group (products keep existing, lose the group)."""
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request method. Only POST requests are allowed."}, status=405)

    group = get_object_or_404(ProductGroup, id=group_id)
    group.delete()
    return JsonResponse({"success": "Gruppe wurde gelöscht."})


@login_required(login_url="login")
def product_delete(request, product_id, slug):
    """Delete a product from the CMS."""
    if request.method != "POST":
        return JsonResponse({"success": False}, status=405)

    product = get_object_or_404(Product, id=product_id, slug=slug)
    product.delete()
    return JsonResponse({"success": True}, status=200)


# =========================================================
# Public product API
# =========================================================

def get_public_filtered_products_queryset(request):
    query = (request.GET.get("q") or request.GET.get("name") or "").strip()
    min_price = (request.GET.get("min_price") or "").strip()
    max_price = (request.GET.get("max_price") or "").strip()
    brand = (request.GET.get("brand") or request.GET.get("manufacturer") or "").strip()
    category = (request.GET.get("category") or "").strip()
    product_type = (request.GET.get("type") or "").strip()
    ordering = (request.GET.get("ordering") or "title_asc").strip()

    is_in_stock_param = request.GET.get("is_in_stock")
    online_only_param = request.GET.get("online_only")
    is_reduced_param = request.GET.get("is_reduced")

    products = (
        Product.objects.filter(is_active=True, original__isnull=True)
        .select_related("brand")
        .prefetch_related("categories", "translations", "translations__categories")
        .annotate(
            effective_price_value=Case(
                When(is_reduced=True, discount_price__isnull=False, then=F("discount_price")),
                default=F("price"),
                output_field=DecimalField(max_digits=10, decimal_places=2),
            )
        )
    )

    if query:
        products = products.filter(
            Q(title__icontains=query)
            | Q(description__icontains=query)
            | Q(brand__name__icontains=query)
            | Q(categories__name__icontains=query)
        ).distinct()

    if min_price:
        min_price_value = parse_decimal(min_price)
        if min_price_value is not None:
            products = products.filter(effective_price_value__gte=min_price_value)

    if max_price:
        max_price_value = parse_decimal(max_price)
        if max_price_value is not None:
            products = products.filter(effective_price_value__lte=max_price_value)

    if brand:
        products = products.filter(Q(brand__slug=brand) | Q(brand__name__icontains=brand))

    if category:
        products = products.filter(Q(categories__slug=category) | Q(categories__name__icontains=category)).distinct()

    if is_in_stock_param not in [None, ""]:
        products = products.filter(is_in_stock=parse_bool(is_in_stock_param))

    if online_only_param not in [None, ""] and parse_bool(online_only_param):
        products = products.filter(online_sell=True)

    if is_reduced_param not in [None, ""] and parse_bool(is_reduced_param):
        products = products.filter(is_reduced=True)

    if product_type == "shop":
        products = products.filter(showcase_only=False)
    elif product_type == "showcase":
        products = products.filter(showcase_only=True)

    ordering_map = {
        "title_asc": "title",
        "title_desc": "-title",
        "price_asc": "effective_price_value",
        "price_desc": "-effective_price_value",
        "updated_desc": "-updated_at",
        "updated_asc": "updated_at",
        "created_desc": "-created_at",
        "created_asc": "created_at",
    }

    return products.order_by(ordering_map.get(ordering, "title")).distinct()

@extend_schema(exclude=True)
@api_view(["GET"])
@authentication_classes([])
@permission_classes([])
def search_products(request):
    queryset = get_public_filtered_products_queryset(request)
    paginator = Paginator(queryset, 12)
    page_obj = paginator.get_page(request.GET.get("page", 1))
    language = get_active_product_language(request)

    data = [
        serialize_public_product(get_localized_product(product, language, require_active=True))
        for product in page_obj.object_list
    ]

    return Response(
        {
            "products": data,
            "pagination": {
                "current_page": page_obj.number,
                "num_pages": paginator.num_pages,
                "has_previous": page_obj.has_previous(),
                "has_next": page_obj.has_next(),
                "previous_page_number": page_obj.previous_page_number() if page_obj.has_previous() else None,
                "next_page_number": page_obj.next_page_number() if page_obj.has_next() else None,
                "total_count": paginator.count,
            },
        },
        status=status.HTTP_200_OK,
    )

def build_grouped_products_context(request):
    """Build the sections for the grouped (showcase) products layout.

    Sections come from ProductGroup (ordered by sort_order); products without
    a group land in "Weitere Produkte" at the end.
    """
    language = get_active_product_language(request)

    products = (
        Product.objects.filter(is_active=True, original__isnull=True)
        .select_related("brand", "group")
        .prefetch_related("categories", "translations", "translations__categories", "translations__group")
        .order_by("-featured", "title")
    )

    grouped = {}
    ungrouped = []

    for product in products:
        # Sections come from the root product's group; display data from the
        # localized variant.
        group = product.group
        localized = get_localized_product(product, language, require_active=True)

        if group is None:
            ungrouped.append(localized)
            continue

        grouped.setdefault(group.id, {"group": group, "products": []})
        grouped[group.id]["products"].append(localized)

    sorted_groups = sorted(
        grouped.values(),
        key=lambda entry: (entry["group"].sort_order, entry["group"].name.lower()),
    )

    return {
        "product_groups": sorted_groups,
        "ungrouped_products": ungrouped,
        "total_products": products.count(),
    }


def public_shop(request):
    shop_settings = ShopSettings.get_solo()

    if shop_settings.is_grouped_layout:
        context = {"shop_settings": shop_settings}
        context.update(build_grouped_products_context(request))
        context.update(get_opening_hours())
        return render(request, "pages/shop_grouped.html", context)

    queryset = get_public_filtered_products_queryset(request)
    paginator = Paginator(queryset, 12)
    page_obj = paginator.get_page(request.GET.get("page", 1))
    language = get_active_product_language(request)
    page_obj.object_list = [
        get_localized_product(product, language, require_active=True)
        for product in page_obj.object_list
    ]

    brands = Brand.objects.filter(products__is_active=True).distinct().order_by("name")
    categories = Category.objects.filter(products__is_active=True).distinct().order_by("name")

    context = {
        "shop_settings": shop_settings,
        "page_obj": page_obj,
        "brands": brands,
        "categories": categories,
        "filters": {
            "q": request.GET.get("q", ""),
            "min_price": request.GET.get("min_price", ""),
            "max_price": request.GET.get("max_price", ""),
            "brand": request.GET.get("brand", ""),
            "category": request.GET.get("category", ""),
            "type": request.GET.get("type", ""),
            "ordering": request.GET.get("ordering", "title_asc"),
            "is_in_stock": parse_bool(request.GET.get("is_in_stock")) if request.GET.get("is_in_stock") not in [None, ""] else False,
            "online_only": parse_bool(request.GET.get("online_only")) if request.GET.get("online_only") not in [None, ""] else False,
            "is_reduced": parse_bool(request.GET.get("is_reduced")) if request.GET.get("is_reduced") not in [None, ""] else False,
        },
    }
    context.update(get_opening_hours())
    return render(request, "pages/shop.html", context)

def detail(request, product_id, slug):
    product = get_object_or_404(
        Product.objects.select_related("brand", "gallery", "original")
        .prefetch_related("categories", "translations", "specifications", "gallery__images"),
        id=product_id,
    )
    # Canonical Slug sicherstellen: alte oder bewusst geänderte Slugs per 301 auf
    # die aktuelle URL umleiten. Die pk in der URL identifiziert das Produkt
    # eindeutig, daher bleiben alte URLs erreichbar statt zu 404en.
    if slug != product.slug:
        return redirect(product.get_absolute_url(), permanent=True)

    last_url = request.META.get('HTTP_REFERER')
    if not product.is_active:
        return render(request, "pages/errors/error.html", {
            "error": "Dieses Produkt ist nicht mehr verfügbar",
            "saveLink": last_url if last_url else '/'
        })
    localized_product = get_localized_product(product, get_active_product_language(request), require_active=True)
    if localized_product.pk != product.pk:
        return redirect(localized_product.get_absolute_url())
    product = localized_product
    context={"product": product}
    context.update(get_opening_hours())
    return render(request, 'pages/detail.html', context)

# =========================================================
# CMS order views
# =========================================================

@login_required(login_url="login")
def order_detail_view(request, order_id):
    """Render the CMS order detail page."""
    order = get_object_or_404(
        Order.objects.select_related("buyer_address").prefetch_related("items__product"),
        id=order_id,
    )
    return render(request, "pages/cms/orders/detail.html", {"order": order})


@login_required(login_url="login")
def order_view(request):
    """Render the CMS order overview with dashboard metrics."""
    line_total_expr = build_order_line_total_expression()

    total_orders = Order.objects.filter(verified=True).count()

    total_revenue = (
        OrderItem.objects.filter(order__verified=True, order__status__in=["COMPLETED", "PAID"])
        .aggregate(total_revenue=Sum(line_total_expr))
        .get("total_revenue")
        or Decimal("0.00")
    )

    total_clients = (
        Order.objects.filter(verified=True)
        .exclude(buyer_email="")
        .values("buyer_email")
        .distinct()
        .count()
    )

    open_orders = Order.objects.filter(status="OPEN", verified=True).count()

    most_bought_products = (
        OrderItem.objects.filter(order__status="COMPLETED", order__verified=True)
        .values("product__title", "product__title_image")
        .annotate(
            total_quantity=Sum("quantity"),
            total_cash=Sum(line_total_expr),
        )
        .order_by("-total_quantity")[:5]
    )

    biggest_buyers = (
        OrderItem.objects.filter(order__verified=True)
        .exclude(order__buyer_email="")
        .values("order__buyer_email")
        .annotate(total_spent=Sum(line_total_expr))
        .order_by("-total_spent")[:5]
    )

    all_orders = Order.objects.filter(verified=True).order_by("-created_at")

    context = {
        "total_orders": total_orders,
        "total_revenue": total_revenue,
        "total_clients": total_clients,
        "open_orders": open_orders,
        "most_bought_products": most_bought_products,
        "biggest_buyers": biggest_buyers,
        "all_orders": all_orders,
    }
    return render(request, "pages/cms/orders/overview.html", context)


# =========================================================
# Admin order API
# =========================================================

@extend_schema(exclude=True)
@api_view(["PATCH"])
@permission_classes([IsAuthenticated])
def update_order_status_admin(request, order_id):
    """Update an order status from the CMS admin area."""
    order = get_object_or_404(Order, id=order_id)
    new_status = request.data.get("status")

    valid_statuses = {choice[0] for choice in Order.STATUS_CHOICES}

    if not new_status:
        return Response({"error": "Es wurde kein Status mitgegeben."}, status=status.HTTP_400_BAD_REQUEST)

    if new_status not in valid_statuses:
        return Response({"error": "Ungültiger Status."}, status=status.HTTP_400_BAD_REQUEST)

    old_status = order.status
    email_sent = False

    if old_status == new_status:
        return Response({"success": "Auftragsstatus wurde nicht verändert."}, status=status.HTTP_200_OK)

    order.status = new_status

    if new_status == "PAID":
        order.paid = True
        send_payment_confirmation(order)
        email_sent = True

    elif new_status == "READY_FOR_PICKUP" and old_status in {"OPEN", "PAID"}:
        send_ready_for_pickup_confirmation(order)
        email_sent = True

    elif new_status == "SHIPPED" and old_status in {"OPEN", "PAID", "READY_FOR_PICKUP"}:
        send_shipping_confirmation(order)
        email_sent = True

    order.save()

    if email_sent:
        return Response(
            {"success": "Auftragsstatus wurde erfolgreich angepasst. Der Käufer hat eine Bestätigungs E Mail erhalten."},
            status=status.HTTP_200_OK,
        )

    return Response({"success": "Auftragsstatus wurde erfolgreich angepasst."}, status=status.HTTP_200_OK)


@extend_schema(exclude=True)
@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def delete_review(request, review_id):
    """Delete a review from the CMS."""
    review = get_object_or_404(Review, pk=review_id)
    review.delete()
    return Response({"success": "Review wurde erfolgreich gelöscht"}, status=status.HTTP_200_OK)


@extend_schema(exclude=True)
@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def delete_order(request, order_id):
    """Delete an order from the CMS."""
    order = get_object_or_404(Order, pk=order_id)
    order.delete()
    return Response({"success": "Auftrag wurde erfolgreich gelöscht"}, status=status.HTTP_200_OK)


@extend_schema(exclude=True)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_order_by_id(request, order_id):
    """Return one order as serialized JSON."""
    order = get_object_or_404(Order, id=order_id)
    serializer = OrderSerializer(order)
    return Response(serializer.data, status=status.HTTP_200_OK)


@extend_schema(exclude=True)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_orders(request):
    """Return filtered orders as JSON for CMS usage."""
    status_filter = request.GET.get("status")
    buyer_email_filter = request.GET.get("buyer_email")
    last_period_filter = request.GET.get("last_period")

    orders = Order.objects.all().order_by("-created_at")

    if status_filter:
        orders = orders.filter(status=status_filter)

    if buyer_email_filter:
        orders = orders.filter(buyer_email=buyer_email_filter)

    if last_period_filter:
        period_map = {
            "1_year": timedelta(days=365),
            "30_days": timedelta(days=30),
            "1_week": timedelta(weeks=1),
            "1_day": timedelta(days=1),
        }

        if last_period_filter not in period_map:
            return Response({"error": "Invalid last_period parameter"}, status=status.HTTP_400_BAD_REQUEST)

        start_date = timezone.now() - period_map[last_period_filter]
        orders = orders.filter(created_at__gte=start_date)

    data = list(orders.values()) if orders.exists() else []
    return JsonResponse(data, safe=False)


# =========================================================
# Public cart and checkout views
# =========================================================

@extend_schema(exclude=True)
@api_view(["POST"])
@authentication_classes([])
@permission_classes([])
def add_to_cart(request, product_id):
    """Add a product to the current session cart."""
    product = get_object_or_404(Product, id=product_id)

    if not product.is_active:
        return JsonResponse({"error": "Dieses Produkt wird aktuell nicht mehr verkauft."}, status=400)

    if not product.is_in_stock:
        return JsonResponse(
            {"error": "Dieses Produkt ist aktuell nicht mehr im Lager verfügbar. Schauen Sie später nochmal vorbei."},
            status=400,
        )

    if product.showcase_only or not product.online_sell:
        return JsonResponse({"error": "Dieses Produkt kann nicht online bestellt werden."}, status=400)

    product_amount_raw = request.data.get("amount") or request.POST.get("amount")
    if not product_amount_raw:
        return JsonResponse({"error": "Bitte gebe die Produktanzahl an."}, status=400)

    try:
        product_amount = int(product_amount_raw)
    except (TypeError, ValueError):
        return JsonResponse({"error": "Die Produktanzahl ist ungültig."}, status=400)

    if product_amount <= 0:
        return JsonResponse({"error": "Die Produktanzahl muss größer 0 sein."}, status=400)

    order = get_or_create_active_cart_order(request)
    cart_amount = int(request.session.get("cart_amount", 0))

    order_item, created = OrderItem.objects.get_or_create(
        order=order,
        product=product,
        defaults={
            "is_discounted": product.is_reduced,
            "unit_price": product.price,
            "discounted_price": product.discount_price if product.is_reduced else None,
            "quantity": product_amount,
        },
    )

    if created:
        request.session["cart_amount"] = cart_amount + 1
    else:
        order_item.quantity += product_amount
        order_item.save()

    serializer = OrderItemSerializer(order_item)

    return JsonResponse(
        {
            "success": f"Produkt wurde {product_amount}x erfolgreich zum Warenkorb hinzugefügt.",
            "order_session_id": request.session["order_id"],
            "order_id": order.id,
            "uuid": str(order.uuid),
            "order_item": serializer.data,
        }
    )


@extend_schema(exclude=True)
@api_view(["GET"])
@authentication_classes([])
@permission_classes([])
def cart_items(request):
    """Return the current cart items for the session."""
    order = get_session_order(request)
    cart_amount = request.session.get("cart_amount", 0)

    if not order:
        return JsonResponse({"error": "Es existiert aktuell kein Warenkorb."}, status=404)

    total_price = float(order.total())
    items = build_cart_items_payload(order)

    return JsonResponse(
        {
            "cart_items": items,
            "cart_amount": cart_amount,
            "total_price": total_price,
            "order_session_id": order.id,
            "order_id": order.id,
        }
    )


def cart_view(request):
    """Render the cart page for the current session order."""
    order = get_session_order(request)

    if not order:
        return render(
            request,
            "pages/errors/error.html",
            {
                "error": "Du hast noch keine Ware im Warenkorb. Füge zuerst welche hinzu.",
                "saveLink": get_last_url(request),
            },
        )

    if order.verified:
        reset_cart_session(request)
        return render(
            request,
            "pages/errors/error.html",
            {
                "error": "Deine Bestellung wurde bereits verifiziert und bestellt. Bitte füge neue Produkte hinzu, um eine neue Bestellung zu tätigen.",
                "saveLink": get_last_url(request),
            },
        )

    context = {"order": order}
    context.update(get_opening_hours())
    return render(request, "pages/cms/orders/cart.html", context)


def cart_verify_success_view(request):
    """Render the cart verification success page."""
    context = {}
    context.update(get_opening_hours())
    return render(request, "pages/cms/orders/success/cart-verify-success.html", context)


@extend_schema(exclude=True)
@api_view(["DELETE"])
@authentication_classes([])
@permission_classes([])
def remove_from_cart(request, order_item_id):
    """Remove one order item from the current session cart."""
    order_item = get_object_or_404(OrderItem, id=order_item_id)
    order_id = request.session.get("order_id")

    if not order_id or order_item.order_id != order_id:
        return JsonResponse({"error": "OrderItem does not belong to the current order."}, status=403)

    order_item.delete()

    cart_amount = int(request.session.get("cart_amount", 0))
    request.session["cart_amount"] = max(cart_amount - 1, 0)

    return JsonResponse({"success": "Produkt wurde erfolgreich vom Warenkorb entfernt."})


@extend_schema(exclude=True)
@api_view(["POST"])
@authentication_classes([])
@permission_classes([])
def update_quantity(request, order_item_id):
    """Update the quantity of a single cart item."""
    order_item = get_object_or_404(OrderItem, id=order_item_id)
    order_id = request.session.get("order_id")

    if not order_id or order_item.order_id != order_id:
        return JsonResponse({"error": "OrderItem does not belong to the current order."}, status=403)

    quantity_raw = request.data.get("quantity") or request.POST.get("quantity", 1)

    try:
        new_quantity = int(quantity_raw)
    except (TypeError, ValueError):
        return JsonResponse({"error": "Quantity is invalid."}, status=400)

    if new_quantity <= 0:
        return JsonResponse({"error": "Quantity must be greater than 0."}, status=400)

    if order_item.product.is_reduced and not order_item.is_discounted:
        return JsonResponse({"error": "Quantity cannot be updated for this product."}, status=400)

    order_item.quantity = new_quantity
    order_item.save()

    return JsonResponse({"success": "Quantity updated successfully."})


@extend_schema(exclude=True)
@api_view(["POST"])
@authentication_classes([])
@permission_classes([])
def update_cart_items(request):
    """Bulk update cart items for the current session order."""
    order = get_session_order(request)
    if not order:
        return JsonResponse({"error": "Order not found in session."}, status=status.HTTP_404_NOT_FOUND)

    cart_items_data_raw = request.data.get("cart_items") or request.POST.get("cart_items", "[]")

    try:
        cart_items_data = json.loads(cart_items_data_raw)
    except json.JSONDecodeError:
        return JsonResponse({"error": "cart_items enthält kein valides JSON."}, status=400)

    with transaction.atomic():
        for item_data in cart_items_data:
            order_item_id = item_data.get("order_item_id")
            new_quantity_raw = item_data.get("quantity", 0)

            try:
                new_quantity = int(new_quantity_raw)
            except (TypeError, ValueError):
                continue

            if new_quantity <= 0:
                continue

            order_item = get_object_or_404(OrderItem, id=order_item_id, order=order)

            if new_quantity != order_item.quantity:
                order_item.quantity = new_quantity
                order_item.save()

    request.session["cart_total_price"] = float(order.total())

    data = {
        "success": "Der Warenkorb wurde erfolgreich aktualisiert.",
        "cart_items": build_cart_items_payload(order),
        "tax": round(float(order.calculate_tax()), 2),
        "total_price": round(float(order.total()), 2),
        "total_discount": round(float(order.total_discount()), 2),
        "total_tax_price": round(float(order.total_with_tax()), 2),
    }

    return JsonResponse(data, status=status.HTTP_200_OK)


@extend_schema(exclude=True)
@api_view(["POST"])
@authentication_classes([])
@permission_classes([])
def verify_cart(request):
    """Send a verification mail for the current cart order."""
    buyer_email = (request.data.get("buyer_email") or request.POST.get("buyer_email") or "").strip()
    buyer_name = (request.data.get("buyer_name") or request.POST.get("buyer_name") or "").strip()

    if not buyer_email or not buyer_name:
        return JsonResponse({"error": "Email und Name müssen angegeben werden."}, status=400)

    order = get_session_order(request)
    if not order:
        return JsonResponse({"error": "Du hast noch keine Produkte im Einkaufswagen."}, status=400)

    if order.status != "OPEN" or order.verified:
        reset_cart_session(request)
        return JsonResponse({"error": "Order ist bereits verifiziert."}, status=400)

    for item in order.items.select_related("product").all():
        if (item.product.is_reduced and not item.is_discounted) or (not item.product.is_reduced and item.is_discounted):
            return JsonResponse({"error": f"Falsche Preiskonfiguration {item.product.title}"}, status=400)

    user_settings = get_public_user_settings()
    if not user_settings:
        return JsonResponse({"error": "Es wurden keine öffentlichen Shop Einstellungen gefunden."}, status=400)

    order.buyer_email = buyer_email
    order.save()

    verification_url = (
        request.scheme
        + "://"
        + request.get_host()
        + reverse("order-verify")
        + f"?token={order.uuid}&order_id={order.id}"
    )

    subject = f"Ihr Auftrag {order.id}"
    message = (
        f"Hallo {buyer_name},\n\n"
        f"Vielen Dank für Ihren Auftrag bei {user_settings.company_name}.\n"
        f"Ihr Auftrag mit der Auftragsnummer #{order.id} wurde erfolgreich bestätigt.\n\n"
        f"Hier sind die Details Ihres Auftrags\n\n"
        f"{build_order_summary(order)}\n\n"
        f"Wir haben Ihren Auftrag erhalten und benötigen noch eine Bestätigung von Ihnen, um fortzufahren.\n"
        f"Bitte klicken Sie auf den folgenden Link, um Ihren Auftrag zu bestätigen und zur Kasse zu gelangen\n"
        f"{verification_url}\n\n"
        f"Nach erfolgreicher Bestätigung können Sie Ihre Ware bestellen oder abholen."
    )
    message += build_contact_signature(user_settings)

    send_mail(
        subject,
        message,
        settings.EMAIL_HOST_USER,
        [buyer_email],
        fail_silently=False,
    )

    reset_cart_session(request)
    return JsonResponse({"success": "Erfolg. Sie erhalten nun bald eine E Mail."})


def order_verify_view(request):
    """Render the final order verification page."""
    token = request.GET.get("token")
    order_id = request.GET.get("order_id")

    order = get_object_or_404(Order, id=order_id, uuid=token)

    if order.verified:
        reset_cart_session(request)
        return render(
            request,
            "pages/errors/error.html",
            {
                "error": (
                    "Diese Bestellung wurde bereits verifiziert und bestellt. "
                    "Für weitere Informationen überprüfe deine E Mails oder schreibe uns eine Nachricht. "
                    f"Status der Bestellung {order.get_status_display()}"
                ),
                "saveLink": get_last_url(request),
            },
        )

    context = {"order": order}
    context.update(get_opening_hours())
    return render(request, "pages/cms/orders/verify.html", context)


def order_verify_success_view(request):
    """Render the final order verification success page."""
    context = {}
    context.update(get_opening_hours())
    return render(request, "pages/cms/orders/success/order-verify-success.html", context)


@extend_schema(exclude=True)
@api_view(["POST"])
@authentication_classes([])
@permission_classes([])
def verify_order(request):
    """Finalize and verify an order after buyer confirmation."""
    order_id = request.data.get("order_id") or request.POST.get("order_id")
    token = request.data.get("token") or request.POST.get("token")
    address = request.data.get("address") or request.POST.get("address")
    city = request.data.get("city") or request.POST.get("city")
    postal_code = request.data.get("postal_code") or request.POST.get("postal_code")
    country = request.data.get("country") or request.POST.get("country")
    prename = request.data.get("buyer_prename") or request.POST.get("buyer_prename")
    name = request.data.get("buyer_name") or request.POST.get("buyer_name")
    shipping = request.data.get("shipping") or request.POST.get("shipping")
    payment = request.data.get("payment") or request.POST.get("payment")

    if not order_id or not token:
        return JsonResponse({"error": "order_id and token are required."}, status=400)

    if not all([address, city, postal_code, country, prename, name]):
        return JsonResponse({"error": "Die Adresse muss angegeben sein."}, status=400)

    valid_shipping = {choice[0] for choice in Order.SHIPPING_CHOICES}
    valid_payment = {choice[0] for choice in Order.PAYMENT_CHOICES}

    if shipping not in valid_shipping:
        return JsonResponse({"error": "Ungültige Versandart."}, status=400)

    if payment not in valid_payment:
        return JsonResponse({"error": "Ungültige Zahlungsart."}, status=400)

    order = get_object_or_404(Order, id=order_id, uuid=token)

    if order.verified:
        return JsonResponse({"error": "Order is already verified."}, status=400)

    user_settings = get_public_user_settings()
    if not user_settings:
        return JsonResponse({"error": "There is no public shop user configuration."}, status=400)

    with transaction.atomic():
        shipping_address, _ = ShippingAddress.objects.get_or_create(
            address=address,
            city=city,
            country=country,
            prename=prename,
            name=name,
            postal_code=postal_code,
        )

        order.verified = True
        order.buyer_address = shipping_address
        order.shipping = shipping
        order.payment = payment
        order.save()

    subject = f"Bestätigung Auftrag {order.id}"
    message = (
        f"Vielen Dank für die Bestätigung Ihres Auftrags #{order.id} bei {user_settings.company_name}.\n\n"
        f"{build_order_summary(order)}\n\n"
        f"Ihre ausgewählte Liefermethode {order.get_shipping_display()}\n"
        f"Ihre ausgewählte Bezahlmethode {order.get_payment_display()}\n"
    )

    if order.payment != "CASH":
        message += (
            "\nWir werden Ihren Auftrag so schnell wie möglich bearbeiten und Ihnen eine Rechnung zukommen lassen.\n"
            "Sobald Sie die Rechnung bezahlt haben und wir die Zahlung erhalten haben, erhalten Sie"
        )
        if order.shipping == "PICKUP":
            message += " eine E Mail, dass Ihre Ware zur Abholung bereit ist."
        elif order.shipping == "SHIPPING":
            message += " eine Benachrichtigung per E Mail, sobald Ihre Bestellung versandt wurde."
    elif order.shipping == "PICKUP":
        message += "\nSie erhalten eine E Mail, sobald Sie Ihre Bestellung abholen können."

    message += build_contact_signature(user_settings)

    send_mail(
        subject,
        message,
        settings.EMAIL_HOST_USER,
        [order.buyer_email],
        fail_silently=False,
    )

    if user_settings.email:
        dashboard_url = settings.DASHBOARD_URL
        subject_company = "Neue Bestellung eingegangen"
        message_company = (
            f"Hallo {user_settings.full_name},\n\n"
            "Eine neue Bestellung ist eingegangen. Bitte schauen Sie im Dashboard nach, um weitere Details zu erhalten.\n\n"
            f"Sie können die Bestellung hier einsehen\n{dashboard_url}cms/orders/{order.id}/\n\n"
            "Vielen Dank.\n\n"
            "Mit freundlichen Grüßen\n"
            "Ihr YooLink"
        )

        send_mail(
            subject_company,
            message_company,
            settings.EMAIL_HOST_USER,
            [user_settings.email],
            fail_silently=False,
        )

    return JsonResponse({"success": "Die Bestellung wurde erfolgreich aufgegeben."})


# =========================================================
# CMS shop dashboard
# =========================================================

@login_required(login_url="login")
def shop(request):
    """Render the CMS shop dashboard."""
    # Only base products (translations are counted via their original) so the
    # numbers match the product overview, which also filters original__isnull=True.
    base_products = Product.objects.filter(original__isnull=True)
    product_stats = base_products.aggregate(
        total=Count("id"),
        active=Count("id", filter=Q(is_active=True)),
        showcase=Count("id", filter=Q(showcase_only=True)),
        out_of_stock=Count("id", filter=Q(is_in_stock=False)),
        online=Count("id", filter=Q(online_sell=True, showcase_only=False)),
        reduced=Count("id", filter=Q(is_reduced=True)),
    )

    verified_orders = Order.objects.filter(verified=True)
    order_stats = verified_orders.aggregate(
        total=Count("id"),
        open=Count("id", filter=~Q(status="COMPLETED")),
    )

    recent_products = list(
        base_products.select_related("brand").order_by("-updated_at")[:5]
    )

    data = {
        "shop_settings": ShopSettings.get_solo(),
        # Backwards-compatible keys
        "product_count": product_stats["total"],
        "order_count": order_stats["total"],
        "order_not_closed_count": order_stats["open"],
        # Richer dashboard context
        "product_stats": product_stats,
        "order_stats": order_stats,
        "recent_products": recent_products,
    }
    return render(request, "pages/cms/shop/shop.html", data)
