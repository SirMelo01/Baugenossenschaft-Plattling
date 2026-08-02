from django.db import models
import hashlib
import secrets
import base64
from datetime import timedelta

# Create your models here.
from django.db.models import Q
from django.db import models
import os
from yoolink.users.models import User
from django.utils.text import slugify
from django.utils import timezone
from django.urls import reverse
from django.core.exceptions import ValidationError
from django.utils.translation import get_language, gettext_lazy as _
from .upload_validation import (
    validate_anyfile_upload,
    validate_subtitle_upload,
    validate_video_thumbnail_upload,
    validate_video_upload,
)

## Produktiv und funktioniert

class FAQ(models.Model):
    question = models.CharField(max_length=255, default="")
    answer = models.TextField(default="")
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order']

    def save(self, *args, **kwargs):
        if not self.id:
            max_order = FAQ.objects.aggregate(models.Max('order'))['order__max']
            self.order = 1 if max_order is None else max_order + 1
        super(FAQ, self).save(*args, **kwargs)

    def __str__(self):
        return self.question

def upload_to_product_image(instance, filename):
    media_uuid = getattr(instance, "media_uuid", None)
    identifier = media_uuid or getattr(instance, "id", "tmp")
    return f"yoolink/products/{identifier}/{filename}"

## Produktiv und funktioniert
def unique_image_name(instance, filename):
    """
    Generate a unique filename by appending a timestamp.
    """
    timestamp = timezone.now().strftime("%Y%m%d%H%M%S")
    base, ext = os.path.splitext(filename)
    return f"yoolink/images/{slugify(base)}_{timestamp}{ext}"

class fileentry(models.Model):
    file = models.ImageField(upload_to=unique_image_name)
    mobile_file = models.ImageField(upload_to=unique_image_name, blank=True, null=True)
    uploaddate = models.DateTimeField(auto_now_add=True)
    title = models.TextField(default="Bildtitel")
    place = models.CharField(max_length=60, default="")

    def __str__(self):
        return os.path.basename(self.file.name)

    @property
    def mobile_file_url(self):
        if not self.mobile_file:
            return ""
        try:
            return self.mobile_file.url
        except ValueError:
            return ""

    @property
    def responsive_srcset(self):
        mobile_url = self.mobile_file_url
        if not mobile_url:
            return ""
        try:
            desktop_url = self.file.url
        except ValueError:
            return ""
        return f"{mobile_url} 900w, {desktop_url} 1920w"

    @property
    def file_extension(self):
        return os.path.splitext(self.file.name)[1].lstrip(".").upper()
    
    def delete(self, *args, **kwargs):
        if self.file:
            self.file.storage.delete(self.file.name)
        if self.mobile_file:
            self.mobile_file.storage.delete(self.mobile_file.name)
        super(fileentry, self).delete(*args, **kwargs)

    def delete_model_only(self, *args, **kwargs):
        super(fileentry, self).delete(*args, **kwargs) 

def unique_anyfile_name(instance, filename):
    timestamp = timezone.now().strftime("%Y%m%d%H%M%S")
    base, ext = os.path.splitext(filename)
    return f"yoolink/uploads/{slugify(base)}_{timestamp}{ext}"

def validate_file_extension(value):
    validate_anyfile_upload(value)
    return
    allowed_extensions = ['.pdf', '.zip', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.txt']
    ext = os.path.splitext(value.name)[1].lower()
    if ext not in allowed_extensions:
        raise ValidationError(f'Dateiformat "{ext}" wird nicht unterstützt.')

class AnyFile(models.Model):
    file = models.FileField(upload_to=unique_anyfile_name, validators=[validate_file_extension])
    uploaded_at = models.DateTimeField(auto_now_add=True)
    title = models.CharField(max_length=200, default="", blank=True)
    description = models.TextField(blank=True)

    def __str__(self):
        return os.path.basename(self.file.name)

    def delete(self, *args, **kwargs):
        self.file.storage.delete(self.file.name)
        super(AnyFile, self).delete(*args, **kwargs)

def unique_video_name(instance, filename):
    timestamp = timezone.now().strftime("%Y%m%d%H%M%S")
    base, ext = os.path.splitext(filename)
    return f"yoolink/videos/{slugify(base)}_{timestamp}{ext}"

def validate_video_extension(value):
    validate_video_upload(value)
    return
    allowed = ['.mp4', '.mov', '.webm']
    ext = os.path.splitext(value.name)[1].lower()
    if ext not in allowed:
        raise ValidationError(f'Dateiformat "{ext}" wird nicht unterstützt.')

def validate_image_extension(value):
    validate_video_thumbnail_upload(value)
    return
    allowed = ['.jpg', '.jpeg', '.png', '.webp']
    ext = os.path.splitext(value.name)[1].lower()
    if ext not in allowed:
        raise ValidationError(f'Bildformat "{ext}" wird nicht unterstützt.')

def validate_vtt_extension(value):
    validate_subtitle_upload(value)
    return
    if not value.name.lower().endswith('.vtt'):
        raise ValidationError('Nur .vtt Untertiteldateien sind erlaubt.')

class VideoFile(models.Model):
    file = models.FileField(
        upload_to=unique_video_name,
        validators=[validate_video_extension],
        help_text="Video-Datei (.mp4, .mov, .webm)"
    )
    thumbnail = models.ImageField(
        upload_to="yoolink/thumbnails/",
        validators=[validate_image_extension],
        blank=True,
        null=True,
        help_text="Poster-Thumbnail für Video"
    )
    subtitle_file = models.FileField(
        upload_to="yoolink/subtitles/",
        validators=[validate_vtt_extension],
        blank=True,
        null=True,
        help_text="Optional: Untertitel im .vtt Format"
    )

    uploaded_at = models.DateTimeField(auto_now_add=True)
    title = models.CharField(max_length=255, help_text="Titel für das Video", blank=True)
    slug = models.SlugField(max_length=255, unique=True, blank=True)
    description = models.TextField(help_text="Beschreibung / Caption des Videos", blank=True)
    duration = models.DurationField(
        blank=True,
        null=True,
        help_text="Laufzeit des Videos (z.B. für SEO oder schema.org)"
    )
    alt_text = models.CharField(max_length=255, help_text="Alt-Text für SEO & Barrierefreiheit", blank=True)
    tags = models.CharField(max_length=255, blank=True, help_text="Kommaseparierte Tags (optional)")
    is_public = models.BooleanField(default=True)
    place = models.CharField(max_length=60, default="")
    autoplay = models.BooleanField(default=False, help_text="Video automatisch abspielen?")
    muted = models.BooleanField(default=False, help_text="Video stumm starten?")
    loop = models.BooleanField(default=False, help_text="Video in Endlosschleife?")
    playsinline = models.BooleanField(default=True, help_text="Video inline abspielen (bes. für iOS)?")
    show_controls = models.BooleanField(default=True, help_text="Standard Video Controls anzeigen?")
    preload = models.CharField(
        max_length=20,
        choices=[('auto', 'Auto'), ('metadata', 'Nur Metadaten'), ('none', 'Nichts')],
        default='metadata',
        help_text="Preload-Verhalten beim Seitenladen"
    )

    def __str__(self):
        return self.title or os.path.basename(self.file.name)

    def save(self, *args, **kwargs):
        if not self.slug and self.title:
            base_slug = slugify(self.title)
            slug = base_slug
            counter = 1
            while VideoFile.objects.filter(slug=slug).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.file:
            self.file.storage.delete(self.file.name)
        if self.thumbnail:
            self.thumbnail.storage.delete(self.thumbnail.name)
        if self.subtitle_file:
            self.subtitle_file.storage.delete(self.subtitle_file.name)
        super().delete(*args, **kwargs)


def upload_to_galery_image(instance, filename):
    """
    Generate a unique filename by appending a timestamp.
    """
    timestamp = timezone.now().strftime("%Y%m%d%H%M%S")
    base, ext = os.path.splitext(filename)
    return f"yoolink/galeryImages/{slugify(base)}_{timestamp}{ext}"

class GaleryImage(models.Model):
    upload = models.ImageField(upload_to=upload_to_galery_image)
    uploaddate = models.DateTimeField(auto_now_add=True)
    title = models.CharField(max_length=200, default="Bildtitel")

    def __str__(self):
        return str(self.pk)
    
    def delete(self, *args, **kwargs):
        self.upload.storage.delete(self.upload.name)
        super(GaleryImage, self).delete(*args, **kwargs)

    def delete_model_only(self, *args, **kwargs):
        super(GaleryImage, self).delete(*args, **kwargs)

class Galerie(models.Model):
    title = models.CharField(max_length=100, default="Titel")
    description = models.TextField(default="")
    active = models.BooleanField(default=True)
    place = models.CharField(max_length=60, default="")
    images = models.ManyToManyField(GaleryImage)
    created_at = models.DateTimeField(auto_now_add=True)
    changed_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title

"""
Blog
"""

def upload_to_blog_image(instance, filename):
    return f"yoolink/blogs/{instance.id}/{filename}"
def default_code():
    return dict()

def generate_unique_blog_slug(instance, base_slug):
    slug = base_slug or "blog"
    unique_slug = slug
    counter = 2
    queryset = Blog.objects.filter(slug=unique_slug)
    if instance.pk:
        queryset = queryset.exclude(pk=instance.pk)

    while queryset.exists():
        unique_slug = f"{slug}-{counter}"
        queryset = Blog.objects.filter(slug=unique_slug)
        if instance.pk:
            queryset = queryset.exclude(pk=instance.pk)
        counter += 1

    return unique_slug

class Blog(models.Model):
    title = models.CharField(max_length=255)
    slug = models.SlugField(unique=True, default='default-slug', max_length=255)
    title_image = models.ImageField(upload_to=upload_to_blog_image, default="", blank=True)
    title_image_alt = models.CharField(max_length=255, default="", blank=True)
    title_image_title = models.CharField(max_length=255, default="", blank=True)
    title_image_caption = models.CharField(max_length=255, default="", blank=True)
    date = models.DateField(auto_now_add=True)  # Automatically set on creation
    last_updated = models.DateField(auto_now=True)  # Automatically updated on save
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    body = models.TextField(default="This Blog is empty")
    markdown = models.TextField(default="", blank=True)
    code = models.JSONField(default=default_code)
    active = models.BooleanField(default=False)
    description = models.TextField(default="")

    language = models.CharField(
        max_length=10,
        default='de',
        choices=[
            ('de', 'Deutsch'),
            ('en', 'English'),
            ('fr', 'Französisch'),
            # weitere Sprachen bei Bedarf
        ]
    )

    original = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='translations',
        help_text=_("Bezieht sich auf den Original-Blog (z.B. auf Deutsch)")
    )

    def delete(self, *args, **kwargs):
        if self.title_image:
            self.title_image.storage.delete(self.title_image.name)
        super(Blog, self).delete(*args, **kwargs)
    
    def __str__(self):
        return self.title + ' | ' + str(self.author)
    
    def save(self, *args, **kwargs):
        # Der Slug wird ausschließlich einmalig bei der Erstellung festgelegt
        # und danach NIE wieder verändert. Dadurch bleibt die öffentliche URL
        # dauerhaft stabil, selbst wenn der Titel später bearbeitet wird.
        # Das verhindert das Google-Problem "Seite mit Weiterleitung", das
        # entsteht, wenn sich der Slug (und damit die URL) nachträglich ändert.
        needs_slug = self._state.adding or not self.slug or self.slug == 'default-slug'
        if needs_slug:
            if self.original:
                base_slug = self.slug if (self.slug and self.slug != 'default-slug') else slugify(self.title)
            else:
                base_slug = slugify(self.title)
            self.slug = generate_unique_blog_slug(self, base_slug)

        super(Blog, self).save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("blog:blog-detail", kwargs={"pk": self.pk, "slug_title": self.slug})

"""
Messages
"""

class Message(models.Model):
    name = models.CharField(max_length=70)
    title = models.CharField(max_length=100, null=True)
    email = models.EmailField(max_length=60)
    message = models.CharField(max_length=3000)
    date = models.DateField(auto_now_add=True, null=True)
    seen = models.BooleanField(default=False)

def upload_to_user_settings(instance, filename):
    return f"yoolink/settings/{instance.id}/{filename}"


def upload_to_website_settings(instance, filename):
    return f"yoolink/website-settings/{instance.id}/{filename}"


class WebsiteSettings(models.Model):
    company_name = models.CharField(max_length=255, default="", blank=True)
    owner_name = models.CharField(max_length=255, default="", blank=True)
    contact_email = models.EmailField(max_length=255, default="", blank=True)
    tel_number = models.CharField(max_length=18, default="", blank=True)
    fax_number = models.CharField(max_length=18, default="", blank=True)
    mobile_number = models.CharField(max_length=18, default="", blank=True)
    website = models.URLField(blank=True, default="")
    address = models.CharField(max_length=255, default="", blank=True)
    social_instagram = models.URLField(blank=True, default="https://www.instagram.com/yoolinkde/")
    social_x = models.URLField(blank=True, default="https://x.com/YooLinkDE")
    social_facebook = models.URLField(blank=True, default="")
    social_linkedin = models.URLField(blank=True, default="")
    price_range = models.CharField(max_length=50, blank=True, default="ab 40 €/Monat")
    area_served = models.CharField(max_length=255, blank=True, default="Passau, Regensburg, Deggendorf, Niederbayern")
    business_description = models.CharField(max_length=255, blank=True, default="Webdesign Agentur im Raum Niederbayern")
    site_meta_description = models.TextField(blank=True, default="")
    site_meta_author = models.CharField(max_length=255, blank=True, default="")
    address_region = models.CharField(max_length=100, blank=True, default="Bayern")
    address_country = models.CharField(max_length=2, blank=True, default="DE")
    geo_latitude = models.CharField(max_length=20, blank=True, default="48.7667")
    geo_longitude = models.CharField(max_length=20, blank=True, default="13.0500")
    vacation = models.BooleanField(default=False)
    vacationText = models.TextField(default="Wir sind aktuell im Urlaub. Ab dem XX.XX sind wir wieder für Sie da!")
    vacation_start = models.DateTimeField(null=True, blank=True)
    vacation_end = models.DateTimeField(null=True, blank=True)
    global_font = models.CharField(max_length=60, default="font-sans", blank=True)
    logo = models.ImageField(upload_to=upload_to_website_settings, default="", blank=True)
    favicon = models.ImageField(upload_to=upload_to_website_settings, default="", blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    @classmethod
    def get_solo(cls):
        settings_obj = cls.objects.order_by("id").first()
        if settings_obj:
            return settings_obj
        return cls.objects.create()

    @classmethod
    def get_site_owner(cls):
        return cls.get_solo()

    @property
    def email(self):
        return self.contact_email

    @email.setter
    def email(self, value):
        self.contact_email = value or ""

    def clean(self):
        if self.vacation_start and self.vacation_end and self.vacation_start > self.vacation_end:
            raise ValidationError("Urlaubsbeginn darf nicht nach dem Urlaubsende liegen.")

    def is_vacation_banner_active(self):
        if not self.vacation:
            return False
        now = timezone.now()
        if self.vacation_start and self.vacation_end:
            return self.vacation_start <= now <= self.vacation_end
        if self.vacation_start and not self.vacation_end:
            return now >= self.vacation_start
        if not self.vacation_start and self.vacation_end:
            return now <= self.vacation_end
        return True

    def __str__(self):
        return self.company_name or "Website Settings"


class UserSettings(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    email = models.EmailField(max_length=255, default='')
    full_name = models.CharField(max_length=255, default='')
    company_name = models.CharField(max_length=255, default='')
    tel_number = models.CharField(max_length=18, default='')
    fax_number = models.CharField(max_length=18, default='')
    mobile_number = models.CharField(max_length=18, default='')
    website = models.URLField(blank=True, default='')
    address = models.CharField(max_length=255, default='')
    # SEO / structured-data profile fields (consumed by ycms.seo_schema)
    social_instagram = models.URLField(blank=True, default='https://www.instagram.com/yoolinkde/')
    social_x = models.URLField(blank=True, default='https://x.com/YooLinkDE')
    social_facebook = models.URLField(blank=True, default='')
    social_linkedin = models.URLField(blank=True, default='')
    price_range = models.CharField(max_length=50, blank=True, default='ab 40 €/Monat')
    area_served = models.CharField(max_length=255, blank=True, default='Passau, Regensburg, Deggendorf, Niederbayern')
    business_description = models.CharField(max_length=255, blank=True, default='Webdesign Agentur im Raum Niederbayern')
    address_region = models.CharField(max_length=100, blank=True, default='Bayern')
    address_country = models.CharField(max_length=2, blank=True, default='DE')
    geo_latitude = models.CharField(max_length=20, blank=True, default='48.7667')
    geo_longitude = models.CharField(max_length=20, blank=True, default='13.0500')
    vacation = models.BooleanField(default=False)
    vacationText = models.TextField(default='Wir sind aktuell im Urlaub. Ab dem XX.XX sind wir wieder für Sie da!')
    vacation_start = models.DateTimeField(null=True, blank=True)
    vacation_end   = models.DateTimeField(null=True, blank=True)
    global_font = models.CharField(max_length=60, default='font-sans')
    logo = models.ImageField(upload_to=upload_to_user_settings, default="", blank=True)
    favicon = models.ImageField(upload_to=upload_to_user_settings, default="", blank=True)

    two_factor_email_enabled = models.BooleanField(default=False)
    two_factor_email_verified = models.BooleanField(default=False)
    two_factor_email_code = models.CharField(max_length=6, blank=True, default='')
    two_factor_email_code_expires_at = models.DateTimeField(null=True, blank=True)
    must_change_password = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(two_factor_email_enabled=False) | ~Q(email=''),
                name='two_factor_requires_email',
            ),
        ]

    @classmethod
    def get_site_owner(cls):
        """
        Returns the settings record that represents the public website owner.

        Older code only considered non-staff users. In this CMS the owner can
        also be a staff/admin account, so we keep non-staff as preferred but
        fall back to the first available settings record.
        """
        preferred_owner = cls.objects.select_related("user").filter(user__is_staff=False).order_by("id").first()
        if preferred_owner:
            return preferred_owner

        return cls.objects.select_related("user").order_by("id").first()

    def __str__(self):
        return f"{self.full_name}'s Einstellungen"
    
    def clean(self):
        if self.vacation_start and self.vacation_end and self.vacation_start > self.vacation_end:
            raise ValidationError("Urlaubsbeginn darf nicht nach dem Urlaubsende liegen.")

        if self.two_factor_email_enabled and not (self.email or '').strip():
            raise ValidationError("Für die E-Mail-2FA muss eine E-Mail-Adresse hinterlegt sein.")
        
    def is_vacation_banner_active(self):
        """true, wenn Toggle an UND wir innerhalb des optionalen Zeitfensters sind."""
        if not self.vacation:
            return False
        now = timezone.now()
        if self.vacation_start and self.vacation_end:
            return self.vacation_start <= now <= self.vacation_end
        if self.vacation_start and not self.vacation_end:
            return now >= self.vacation_start
        if not self.vacation_start and self.vacation_end:
            return now <= self.vacation_end
        return True  # kein Fenster gesetzt -> sichtbar solange Toggle an


CMS_PERMISSION_CHOICES = [
    ("dashboard.view", "Dashboard anzeigen"),
    ("pages.edit", "Seiten bearbeiten"),
    ("blog.edit", "Blogs verwalten"),
    ("media.edit", "Medien verwalten"),
    ("buttons.edit", "Buttons verwalten"),
    ("shop.view", "Shop anzeigen"),
    ("products.edit", "Produkte verwalten"),
    ("orders.edit", "Bestellungen verwalten"),
    ("team.edit", "Team verwalten"),
    ("pricing.edit", "Preise verwalten"),
    ("faq.edit", "FAQ verwalten"),
    ("opening_hours.edit", "Öffnungszeiten verwalten"),
    ("notifications.view", "Benachrichtigungen anzeigen"),
    ("website_settings.edit", "Website-Einstellungen verwalten"),
    ("recovery.manage", "Backups und Recovery verwalten"),
    ("security.edit", "Eigene Sicherheit verwalten"),
    ("developer.manage", "Developer Settings verwalten"),
    ("users.manage", "Benutzer verwalten"),
    ("roles.manage", "Rollen verwalten"),
]

OWNER_PERMISSIONS = [code for code, _label in CMS_PERMISSION_CHOICES]
EDITOR_PERMISSIONS = [
    "dashboard.view",
    "pages.edit",
    "blog.edit",
    "media.edit",
    "buttons.edit",
    "faq.edit",
    "notifications.view",
    "security.edit",
]
SHOP_MANAGER_PERMISSIONS = [
    "dashboard.view",
    "shop.view",
    "products.edit",
    "orders.edit",
    "media.edit",
    "notifications.view",
    "security.edit",
]
DEVELOPER_PERMISSIONS = [
    "dashboard.view",
    "developer.manage",
    "notifications.view",
    "security.edit",
]
VIEWER_PERMISSIONS = [
    "dashboard.view",
    "notifications.view",
    "security.edit",
]
RECOVERY_MANAGER_PERMISSIONS = [
    "dashboard.view",
    "recovery.manage",
    "notifications.view",
    "security.edit",
]

SYSTEM_ROLE_DEFAULTS = {
    "owner": {"name": "OWNER", "permissions": OWNER_PERMISSIONS},
    "editor": {"name": "EDITOR", "permissions": EDITOR_PERMISSIONS},
    "shop-manager": {"name": "SHOP MANAGER", "permissions": SHOP_MANAGER_PERMISSIONS},
    "developer": {"name": "DEVELOPER", "permissions": DEVELOPER_PERMISSIONS},
    "recovery-manager": {"name": "RECOVERY MANAGER", "permissions": RECOVERY_MANAGER_PERMISSIONS},
    "viewer": {"name": "VIEWER", "permissions": VIEWER_PERMISSIONS},
}


class CMSRole(models.Model):
    name = models.CharField(max_length=80)
    slug = models.SlugField(max_length=90, unique=True)
    description = models.TextField(blank=True, default="")
    permissions = models.JSONField(default=list, blank=True)
    is_system = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        valid_permissions = {code for code, _label in CMS_PERMISSION_CHOICES}
        self.permissions = sorted(set(self.permissions or []) & valid_permissions)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class CMSUserRole(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="cms_role_assignments")
    role = models.ForeignKey(CMSRole, on_delete=models.CASCADE, related_name="user_assignments")
    assigned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "role")
        ordering = ["user__username", "role__name"]

    def __str__(self):
        return f"{self.user} -> {self.role}"


class RecoveryBackup(models.Model):
    TRIGGER_SCHEDULED = "scheduled"
    TRIGGER_MANUAL = "manual"
    TRIGGER_CHOICES = [
        (TRIGGER_SCHEDULED, "Automatisch"),
        (TRIGGER_MANUAL, "Manuell"),
    ]

    STATUS_QUEUED = "queued"
    STATUS_RUNNING = "running"
    STATUS_SUCCEEDED = "succeeded"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = [
        (STATUS_QUEUED, "Wartet"),
        (STATUS_RUNNING, "Läuft"),
        (STATUS_SUCCEEDED, "Erfolgreich"),
        (STATUS_FAILED, "Fehlgeschlagen"),
    ]

    trigger = models.CharField(max_length=20, choices=TRIGGER_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_QUEUED)
    slot = models.PositiveSmallIntegerField(null=True, blank=True)
    object_key = models.CharField(max_length=500, blank=True, default="")
    filename = models.CharField(max_length=180, blank=True, default="")
    size_bytes = models.PositiveBigIntegerField(default=0)
    encrypted_sha256 = models.CharField(max_length=64, blank=True, default="")
    include_media = models.BooleanField(default=False)
    storage_bucket = models.CharField(max_length=255, blank=True, default="")
    storage_endpoint = models.CharField(max_length=255, blank=True, default="")
    error_message = models.TextField(blank=True, default="")
    created_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="recovery_backups",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Recovery Backup {self.id} ({self.status})"


class DeveloperApiKey(models.Model):
    READ = "read"
    WRITE = "write"
    APP_BLOG = "blog"
    APP_BLOGS = APP_BLOG
    LEGACY_APP_BLOGS = "blogs"
    TOKEN_PREFIX = "yl_live"

    ACCESS_LEVEL_CHOICES = [
        (READ, "Nur lesen"),
        (WRITE, "Lesen und schreiben"),
    ]
    APP_CHOICES = [
        (APP_BLOG, "Blog"),
    ]

    name = models.CharField(max_length=120)
    prefix = models.CharField(max_length=32, unique=True, editable=False)
    key_hash = models.CharField(max_length=64, unique=True, editable=False)
    created_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="developer_api_keys",
    )
    access_level = models.CharField(
        max_length=10,
        choices=ACCESS_LEVEL_CHOICES,
        default=READ,
    )
    allowed_apps = models.JSONField(default=list)
    expires_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Developer API Key"
        verbose_name_plural = "Developer API Keys"

    def __str__(self):
        return f"{self.name} ({self.prefix})"

    @classmethod
    def make_key_hash(cls, raw_key):
        return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()

    @classmethod
    def extract_prefix(cls, raw_key):
        if not raw_key:
            return ""

        parts = raw_key.split("_", 3)
        if len(parts) != 4 or f"{parts[0]}_{parts[1]}" != cls.TOKEN_PREFIX:
            return ""

        return parts[2]

    @classmethod
    def issue_key(cls, *, created_by, name, access_level, allowed_apps, expires_at=None):
        allowed_values = {choice[0] for choice in cls.APP_CHOICES}
        normalized_apps = sorted(set(allowed_apps or []) & allowed_values)

        if not normalized_apps:
            normalized_apps = [cls.APP_BLOG]

        while True:
            prefix = secrets.token_hex(6)
            if not cls.objects.filter(prefix=prefix).exists():
                break

        raw_key = f"{cls.TOKEN_PREFIX}_{prefix}_{secrets.token_urlsafe(32)}"
        api_key = cls.objects.create(
            created_by=created_by,
            name=name,
            prefix=prefix,
            key_hash=cls.make_key_hash(raw_key),
            access_level=access_level,
            allowed_apps=normalized_apps,
            expires_at=expires_at,
        )
        return api_key, raw_key

    @property
    def token_hint(self):
        return f"{self.TOKEN_PREFIX}_{self.prefix}_..."

    def is_expired(self):
        return bool(self.expires_at and self.expires_at <= timezone.now())

    def is_revoked(self):
        return self.revoked_at is not None

    def is_usable(self):
        return not self.is_revoked() and not self.is_expired()

    def allows_app(self, app_code):
        allowed_apps = self.allowed_apps or []
        if app_code == self.APP_BLOG and self.LEGACY_APP_BLOGS in allowed_apps:
            return True
        return app_code in allowed_apps

    def allows_write(self):
        return self.access_level == self.WRITE

    def revoke(self):
        if not self.revoked_at:
            self.revoked_at = timezone.now()
            self.save(update_fields=["revoked_at", "updated_at"])


class DeveloperApiConnectAuthorization(models.Model):
    CODE_TTL_MINUTES = 10
    CODE_PREFIX = "yl_connect"
    METHOD_S256 = "S256"

    CODE_CHALLENGE_METHOD_CHOICES = [
        (METHOD_S256, "S256"),
    ]

    client_name = models.CharField(max_length=160)
    redirect_uri = models.URLField(max_length=2048)
    state = models.CharField(max_length=500, blank=True)
    code_challenge = models.CharField(max_length=128)
    code_challenge_method = models.CharField(
        max_length=12,
        choices=CODE_CHALLENGE_METHOD_CHOICES,
        default=METHOD_S256,
    )
    code_hash = models.CharField(max_length=64, unique=True, editable=False)
    created_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="developer_api_connect_authorizations",
    )
    access_level = models.CharField(
        max_length=10,
        choices=DeveloperApiKey.ACCESS_LEVEL_CHOICES,
        default=DeveloperApiKey.READ,
    )
    allowed_apps = models.JSONField(default=list)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Developer API Connect Authorization"
        verbose_name_plural = "Developer API Connect Authorizations"

    def __str__(self):
        return f"{self.client_name} für {self.created_by}"

    @classmethod
    def make_code_hash(cls, raw_code):
        return hashlib.sha256(raw_code.encode("utf-8")).hexdigest()

    @classmethod
    def issue_code(
        cls,
        *,
        created_by,
        client_name,
        redirect_uri,
        code_challenge,
        code_challenge_method=METHOD_S256,
        access_level=DeveloperApiKey.READ,
        allowed_apps=None,
        state="",
    ):
        allowed_values = {choice[0] for choice in DeveloperApiKey.APP_CHOICES}
        normalized_apps = sorted(set(allowed_apps or []) & allowed_values)
        if not normalized_apps:
            normalized_apps = [DeveloperApiKey.APP_BLOG]

        while True:
            raw_code = f"{cls.CODE_PREFIX}_{secrets.token_urlsafe(32)}"
            code_hash = cls.make_code_hash(raw_code)
            if not cls.objects.filter(code_hash=code_hash).exists():
                break

        authorization = cls.objects.create(
            created_by=created_by,
            client_name=client_name,
            redirect_uri=redirect_uri,
            state=state or "",
            code_challenge=code_challenge,
            code_challenge_method=code_challenge_method,
            code_hash=code_hash,
            access_level=access_level,
            allowed_apps=normalized_apps,
            expires_at=timezone.now() + timedelta(minutes=cls.CODE_TTL_MINUTES),
        )
        return authorization, raw_code

    @classmethod
    def pkce_s256(cls, code_verifier):
        digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
        return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")

    def is_usable(self):
        return self.used_at is None and self.expires_at > timezone.now()

    def verify_code_verifier(self, code_verifier):
        if self.code_challenge_method != self.METHOD_S256:
            return False
        return secrets.compare_digest(self.pkce_s256(code_verifier), self.code_challenge)

    def mark_used(self):
        self.used_at = timezone.now()
        self.save(update_fields=["used_at"])

class OpeningHours(models.Model):
    DAY_CHOICES = [
        ('MON', 'Montag'),
        ('TUE', 'Dienstag'),
        ('WED', 'Mittwoch'),
        ('THU', 'Donnerstag'),
        ('FRI', 'Freitag'),
        ('SAT', 'Samstag'),
        ('SUN', 'Sonntag'),
    ]
    
    website = models.ForeignKey(WebsiteSettings, on_delete=models.CASCADE, related_name='opening_hours', null=True, blank=True)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, related_name='opening_hours', null=True, blank=True)
    day = models.CharField(max_length=3, choices=DAY_CHOICES)
    is_open = models.BooleanField(default=False)
    start_time = models.TimeField(default='08:00')  # Set default start time to 8 o'clock
    end_time = models.TimeField(default='14:00')    # Set default end time to 14 o'clock
    has_lunch_break = models.BooleanField(default=False)
    lunch_break_start = models.TimeField(blank=True, null=True)
    lunch_break_end = models.TimeField(blank=True, null=True)
    
    def calculate_opening_periods(self):
        """
        Berechnet die Öffnungszeiten mit Berücksichtigung der Mittagspause.
        Gibt eine Liste von Zeiträumen zurück, z. B. [(08:00, 12:00), (13:00, 18:00)].
        """
        if self.is_open:
            if self.has_lunch_break and self.lunch_break_start and self.lunch_break_end:
                return [
                    (self.start_time, self.lunch_break_start),
                    (self.lunch_break_end, self.end_time),
                ]
            return [(self.start_time, self.end_time)]
        return []

    def get_day(self):
        return dict(self.DAY_CHOICES)[self.day]

    def __str__(self):
        return f"Opening hours on {self.get_day_display()}"

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["website", "day"], name="unique_opening_hours_per_website_day"),
        ]
    
class TeamMember(models.Model):
    full_name = models.CharField(max_length=120, default='')
    active = models.BooleanField(default=True)
    image = models.CharField(max_length=200, default='')
    age = models.PositiveIntegerField(null=True, blank=True)
    email = models.EmailField(unique=True, null=True)
    years_with_team = models.PositiveIntegerField(default=0)
    position = models.CharField(max_length=100, default="Mitarbeiter")
    note = models.TextField(default="")

    display_order = models.PositiveIntegerField(default=0, db_index=True)

    def __str__(self):
        return self.full_name
    
    class Meta:
        ordering = ["display_order", "id"]
    
from django.db import models


class PricingCard(models.Model):
    title = models.CharField(max_length=100, verbose_name="Titel")
    monthly_price = models.CharField(max_length=20, verbose_name="Monatlicher Preis", help_text="z.B. '25 €' oder '? €'")
    one_time_price = models.CharField(max_length=50, verbose_name="Einmalzahlung", help_text="z.B. '250 €' oder '? €'")
    description = models.TextField(verbose_name="Beschreibung", blank=True, help_text="Kleiner Infotext unter dem Button")
    order = models.PositiveIntegerField(default=0, verbose_name="Reihenfolge", help_text="Reihenfolge der Karte auf der Seite")
    animation = models.CharField(
        max_length=50,
        choices=[
            ('fade-right', 'Fade Right'),
            ('fade-left', 'Fade Left'),
            ('zoom-in', 'Zoom In'),
            ('fade-up', 'Fade Up'),
        ],
        default='fade-up',
        verbose_name="AOS-Animation"
    )
    animation_delay = models.PositiveIntegerField(default=100, verbose_name="Animationsverzögerung (ms)")
    button = models.ForeignKey(
        'Button',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Zugehöriger Button"
    )
    active = models.BooleanField(default=True, verbose_name="Aktiv")

    def __str__(self):
        return self.title

    class Meta:
        ordering = ['order']
        verbose_name = "Pricing-Karte"
        verbose_name_plural = "Pricing-Karten"


class PricingFeature(models.Model):
    pricing_card = models.ForeignKey(PricingCard, related_name='features', on_delete=models.CASCADE)
    text = models.CharField(max_length=200, verbose_name="Featuretext")
    order = models.PositiveIntegerField(default=0, verbose_name="Reihenfolge")

    def __str__(self):
        return f"{self.pricing_card.title}: {self.text}"

    class Meta:
        ordering = ['order']
        verbose_name = "Feature"
        verbose_name_plural = "Features"

class PageLink(models.Model):
    """Vom CMS verwaltbares internes Link-Ziel (z.B. eine Seite oder ein Abschnitt
    einer Seite), das Redakteure bei Buttons ohne URL-Kenntnisse auswählen können."""
    title = models.CharField(
        max_length=120,
        verbose_name="Titel",
        help_text="Anzeigename in der Auswahl, z.B. 'Startseite – Preise'"
    )
    path = models.CharField(
        max_length=300,
        verbose_name="Seitenpfad",
        help_text="Pfad der Seite, z.B. '/' oder '/kontakt/'"
    )
    anchor = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Anker (optional)",
        help_text="Abschnitt auf der Seite ohne '#', z.B. 'preise'"
    )
    order = models.PositiveIntegerField(default=0, verbose_name="Reihenfolge")

    @property
    def url(self):
        path = self.path or "/"
        if self.anchor:
            return f"{path}#{self.anchor.lstrip('#')}"
        return path

    def __str__(self):
        return f"{self.title} ({self.url})"

    class Meta:
        ordering = ["order", "title"]
        verbose_name = "Seiten-Link"
        verbose_name_plural = "Seiten-Links"


class Button(models.Model):
    COLOR_CHOICES = [
        ("blue", "Blau"),
        ("navy", "Dunkelblau"),
        ("dark", "Schwarz"),
        ("emerald", "Grün"),
        ("white", "Weiß"),
        ("outline", "Umrandet"),
        ("link", "Textlink"),
    ]

    text = models.CharField(max_length=100, verbose_name="Button-Text")
    place = models.CharField(
        max_length=100,
        blank=True,
        default="",
        db_index=True,
        verbose_name="Platzierung",
        help_text="Optionaler Slot-Schlüssel, an dem dieser Button auf einer Seite erscheint (z.B. 'main_cmsinfo_hero_cta')."
    )
    color = models.CharField(
        max_length=20,
        choices=COLOR_CHOICES,
        default="blue",
        verbose_name="Farbe"
    )
    page_link = models.ForeignKey(
        PageLink,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="buttons",
        verbose_name="Interne Seite",
        help_text="Internes Link-Ziel; hat Vorrang vor der eigenen URL"
    )
    url = models.CharField(
        max_length=500,
        blank=True,
        verbose_name="Eigene URL",
        help_text="Beliebiger Link, z.B. https://example.com oder mailto:info@example.com"
    )
    hover_text = models.CharField(
        max_length=200,
        verbose_name="Tooltip (Hover-Text)",
        blank=True,
        help_text="Optionaler Text, der beim Hover angezeigt wird"
    )
    target = models.CharField(
        max_length=20,
        choices=[
            ("_self", "Gleicher Tab"),
            ("_blank", "Neuer Tab"),
        ],
        default="_self",
        verbose_name="Link-Ziel"
    )
    icon = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Icon (optional)",
        help_text="Bootstrap-Icon-Klasse, z.B. 'bi bi-arrow-right'"
    )
    order = models.PositiveIntegerField(default=0, verbose_name="Reihenfolge")

    @property
    def href(self):
        if self.page_link:
            return self.page_link.url
        return self.url or "#"

    def __str__(self):
        return f"{self.text} → {self.href}"

    class Meta:
        ordering = ["order"]
        verbose_name = "Button"
        verbose_name_plural = "Buttons"
