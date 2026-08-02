import uuid
from decimal import Decimal, ROUND_HALF_EVEN

from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.urls import reverse
from django.utils.text import slugify


MONEY_QUANT = Decimal("0.01")
TAX_RATE = Decimal("0.19")
SHIPPING_TIERS = (
    (Decimal("2"), Decimal("5.49")),
    (Decimal("5"), Decimal("6.99")),
    (Decimal("10"), Decimal("10.49")),
    (Decimal("31.5"), Decimal("19.99")),
    (Decimal("50.5"), Decimal("19.99")),
)


def to_money(value):
    return Decimal(str(value or "0")).quantize(MONEY_QUANT, rounding=ROUND_HALF_EVEN)


def generate_unique_slug(model_class, value, instance_pk=None):
    base_slug = slugify(value)[:240] or str(uuid.uuid4())[:8]
    slug = base_slug
    counter = 2

    queryset = model_class.objects.all()
    if instance_pk:
        queryset = queryset.exclude(pk=instance_pk)

    while queryset.filter(slug=slug).exists():
        suffix = f"-{counter}"
        slug = f"{base_slug[:255 - len(suffix)]}{suffix}"
        counter += 1

    return slug


def upload_to_product_image(instance, filename):
    return f"yoolink/products/{instance.media_uuid}/{filename}"


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Category(TimeStampedModel):
    name = models.CharField(max_length=255, unique=True)
    slug = models.SlugField(max_length=255, unique=True, blank=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "Categories"

    def save(self, *args, **kwargs):
        self.slug = generate_unique_slug(Category, self.name, self.pk)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Brand(TimeStampedModel):
    name = models.CharField(max_length=255, unique=True)
    website = models.URLField(blank=True)
    slug = models.SlugField(max_length=255, unique=True, blank=True)

    class Meta:
        ordering = ["name"]

    def save(self, *args, **kwargs):
        self.slug = generate_unique_slug(Brand, self.name, self.pk)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class ProductGroup(TimeStampedModel):
    """
    Gruppierung for the public grouped products layout.

    Separate from Category on purpose: categories are filter tags, groups
    define the sections (and their order) on the grouped products page.
    """

    name = models.CharField(max_length=255, unique=True)
    slug = models.SlugField(max_length=255, unique=True, blank=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "name"]
        verbose_name = "Produktgruppe"
        verbose_name_plural = "Produktgruppen"

    def save(self, *args, **kwargs):
        self.slug = generate_unique_slug(ProductGroup, self.name, self.pk)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class ShopSettings(TimeStampedModel):
    """Site wide settings for the public product pages (singleton)."""

    class ProductsLayout(models.TextChoices):
        FILTER = "filter", "Shop mit Filterleiste"
        GROUPED = "grouped", "Gruppiert nach Kategorien"

    products_layout = models.CharField(
        max_length=20,
        choices=ProductsLayout.choices,
        default=ProductsLayout.FILTER,
    )
    products_title = models.CharField(max_length=120, default="Produkte")
    products_intro = models.TextField(blank=True)

    class Meta:
        verbose_name = "Shop Einstellungen"
        verbose_name_plural = "Shop Einstellungen"

    @classmethod
    def get_solo(cls):
        settings_obj = cls.objects.order_by("id").first()
        if settings_obj is None:
            settings_obj = cls.objects.create()
        return settings_obj

    @property
    def is_grouped_layout(self):
        return self.products_layout == self.ProductsLayout.GROUPED

    def __str__(self):
        return f"Shop Einstellungen ({self.get_products_layout_display()})"


class Product(TimeStampedModel):
    media_uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)

    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True, blank=True)
    description = models.TextField(blank=True)
    sku = models.CharField("Artikelnummer", max_length=64, blank=True, default="")
    price_note = models.CharField(
        "Preishinweis",
        max_length=120,
        blank=True,
        default="",
        help_text='Optionaler Zusatz zum Preis, z.B. "pro Stück" oder "zzgl. Versand".',
    )
    featured = models.BooleanField(default=False)
    language = models.CharField(
        max_length=10,
        default="de",
        choices=[
            ("de", "Deutsch"),
            ("en", "Englisch"),
        ],
    )
    original = models.ForeignKey(
        "self",
        blank=True,
        null=True,
        on_delete=models.CASCADE,
        related_name="translations",
    )

    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    discount_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True,
        validators=[MinValueValidator(Decimal("0.01"))],
    )

    title_image = models.ImageField(upload_to=upload_to_product_image, blank=True)
    gallery = models.ForeignKey(
        "ycms.Galerie",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="products",
    )

    is_reduced = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    is_in_stock = models.BooleanField(default=True)
    # Repurposed: "Produkt kann an Kunden geliefert werden" (info flag, no
    # online purchase implied while the shop runs showcase-only).
    online_sell = models.BooleanField(default=False)

    showcase_only = models.BooleanField(default=True)
    show_price_when_showcase = models.BooleanField(default=True)

    categories = models.ManyToManyField(
        Category,
        related_name="products",
        blank=True,
    )
    group = models.ForeignKey(
        ProductGroup,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="products",
    )
    brand = models.ForeignKey(
        Brand,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="products",
    )

    weight = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        default=Decimal("0.0000"),
        validators=[MinValueValidator(Decimal("0"))],
    )

    files = models.ManyToManyField(
        "ycms.AnyFile",
        related_name="products",
        blank=True,
    )

    class Meta:
        ordering = ["title"]

    def clean(self):
        if self.original_id and self.original_id == self.pk:
            raise ValidationError({"original": "Ein Produkt kann nicht seine eigene Übersetzung sein."})

        if self.is_reduced and self.discount_price is None:
            raise ValidationError(
                {"discount_price": "Ein reduzierter Artikel braucht einen Rabattpreis."}
            )

        if self.discount_price is not None and self.discount_price >= self.price:
            raise ValidationError(
                {"discount_price": "Der Rabattpreis muss kleiner als der reguläre Preis sein."}
            )

    def save(self, *args, **kwargs):
        # Slug wird nur bei der Erstellung (oder wenn noch keiner existiert) aus
        # dem Titel erzeugt. Danach bleibt er stabil, auch wenn der Titel später
        # bearbeitet wird – die öffentliche URL ändert sich also nicht ungewollt.
        # Ein Slug kann trotzdem jederzeit bewusst gesetzt/geändert werden (ein
        # explizit vergebener Slug wird hier nicht überschrieben); die Detail-View
        # leitet abweichende/alte Slugs per 301 auf den aktuellen um, da die pk in
        # der URL das Produkt eindeutig identifiziert. Kein Sprach-Suffix mehr –
        # die Sprache steckt bereits im URL-Pfad (z. B. /en/products/...).
        if not self.slug:
            self.slug = generate_unique_slug(Product, self.title, self.pk)

        if not self.is_reduced:
            self.discount_price = None

        self.full_clean()
        super().save(*args, **kwargs)

    @property
    def effective_price(self):
        if self.is_reduced and self.discount_price is not None:
            return self.discount_price
        return self.price

    @property
    def should_show_price_card(self):
        return (not self.showcase_only) or self.show_price_when_showcase

    @property
    def should_show_purchase_controls(self):
        return not self.showcase_only

    def get_absolute_url(self):
        return reverse(
            "product-detail",
            kwargs={"product_id": self.pk, "slug": self.slug},
        )

    def __str__(self):
        return self.title


class ShippingAddress(TimeStampedModel):
    prename = models.CharField(max_length=50)
    name = models.CharField(max_length=50)
    address = models.CharField(max_length=100)
    address2 = models.CharField(max_length=100, blank=True)
    city = models.CharField(max_length=50)
    postal_code = models.CharField(max_length=20)
    country = models.CharField(max_length=50)
    phone_number = models.CharField(max_length=30, blank=True)

    class Meta:
        ordering = ["name", "prename", "city"]

    def __str__(self):
        return f"{self.prename} {self.name}"

    def get_shipping_address(self):
        address_parts = [self.address]
        if self.address2:
            address_parts.append(self.address2)

        address_line = ", ".join(address_parts)
        return f"{address_line}, {self.postal_code} {self.city}, {self.country}"

    def get_buyer_name(self):
        return f"{self.prename} {self.name}"


class Order(TimeStampedModel):
    class Status(models.TextChoices):
        OPEN = "OPEN", "Offen"
        PAID = "PAID", "Bezahlt"
        READY_FOR_PICKUP = "READY_FOR_PICKUP", "Bereit zur Abholung"
        SHIPPED = "SHIPPED", "Versendet"
        COMPLETED = "COMPLETED", "Abgeschlossen"

    class ShippingMethod(models.TextChoices):
        SHIPPING = "SHIPPING", "Lieferung"
        PICKUP = "PICKUP", "Abholung"

    class PaymentMethod(models.TextChoices):
        TRANSFER = "TRANSFER", "Überweisung / PayPal"
        CASH = "CASH", "Barzahlung"

    STATUS_CHOICES = Status.choices
    SHIPPING_CHOICES = ShippingMethod.choices
    PAYMENT_CHOICES = PaymentMethod.choices

    buyer_email = models.EmailField(blank=True)
    buyer_address = models.ForeignKey(
        ShippingAddress,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="orders",
    )

    verified = models.BooleanField(default=False)
    paid = models.BooleanField(default=False)

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.OPEN,
    )
    payment = models.CharField(
        max_length=20,
        choices=PaymentMethod.choices,
        default=PaymentMethod.CASH,
    )
    shipping = models.CharField(
        max_length=20,
        choices=ShippingMethod.choices,
        default=ShippingMethod.SHIPPING,
    )

    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Order #{self.pk} | {self.buyer_email or 'guest'} | {self.status}"

    def subtotal_gross(self):
        return to_money(sum((item.subtotal() for item in self.items.all()), Decimal("0.00")))

    def total_without_shipping(self):
        return self.subtotal_gross()

    def total_weight_kg(self):
        return sum((item.product_weight() for item in self.items.all()), Decimal("0.0000"))

    def shipping_price(self):
        if self.shipping == self.ShippingMethod.PICKUP:
            return to_money(Decimal("0"))

        total_weight_kg = self.total_weight_kg()

        for max_weight, price in SHIPPING_TIERS:
            if total_weight_kg <= max_weight:
                return to_money(price)

        return to_money(SHIPPING_TIERS[-1][1])

    def total(self):
        return to_money(self.subtotal_gross() + self.shipping_price())

    def total_net(self):
        gross_total = self.total()
        divisor = Decimal("1.00") + TAX_RATE
        return to_money(gross_total / divisor)

    def total_with_tax(self):
        return self.total_net()

    def calculate_tax(self):
        return to_money(self.total() - self.total_net())

    def total_discount(self):
        return to_money(sum((item.discount_total() for item in self.items.all()), Decimal("0.00")))

    def total_quantity(self):
        return sum((item.quantity for item in self.items.all()), 0)


class OrderItem(TimeStampedModel):
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="items",
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name="order_items",
    )
    quantity = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1)],
    )

    is_discounted = models.BooleanField(default=False)

    unit_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    discounted_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True,
        validators=[MinValueValidator(Decimal("0.01"))],
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["order", "product"],
                name="unique_product_per_order",
            )
        ]

    def clean(self):
        if self.is_discounted and self.discounted_price is None:
            raise ValidationError(
                {"discounted_price": "Für rabattierte Positionen muss discounted_price gesetzt sein."}
            )

        if not self.is_discounted:
            self.discounted_price = None

        if (
            self.discounted_price is not None
            and self.discounted_price >= self.unit_price
        ):
            raise ValidationError(
                {"discounted_price": "discounted_price muss kleiner als unit_price sein."}
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def get_price(self):
        if self.is_discounted and self.discounted_price is not None:
            return self.discounted_price
        return self.unit_price

    def subtotal(self):
        return to_money(self.get_price() * self.quantity)

    def discount_total(self):
        if self.is_discounted and self.discounted_price is not None:
            return to_money((self.unit_price - self.discounted_price) * self.quantity)
        return to_money(Decimal("0"))

    def product_weight(self):
        if not self.product.weight:
            return Decimal("0.0000")
        return self.product.weight * self.quantity

    def __str__(self):
        return f"{self.product.title} | Menge {self.quantity}"


class Review(TimeStampedModel):
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="reviews",
    )
    user_name = models.CharField(max_length=255)
    email = models.EmailField()
    comment = models.TextField(blank=True)
    rating = models.PositiveSmallIntegerField(
        default=5,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user_name} | {self.product.title} | {self.rating} Sterne"#
    
class ProductSpecification(TimeStampedModel):
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="specifications",
    )
    key = models.CharField(max_length=120)
    value = models.CharField(max_length=255)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "id"]

    def clean(self):
        self.key = (self.key or "").strip()
        self.value = (self.value or "").strip()

        if not self.key:
            raise ValidationError({"key": "Die Bezeichnung der Spezifikation darf nicht leer sein."})

        if not self.value:
            raise ValidationError({"value": "Der Wert der Spezifikation darf nicht leer sein."})

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.product.title} | {self.key} = {self.value}"
