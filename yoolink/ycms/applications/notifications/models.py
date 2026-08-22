from django.db import models
from django.urls import reverse

from yoolink.ycms.applications.shop.models import Order
from yoolink.ycms.models import CONTACT_CATEGORY_META, Message


class NotificationQuerySet(models.QuerySet):
    def unread(self):
        return self.filter(seen=False, is_spam=False)

    def latest_first(self):
        return self.order_by("-created_at")

    def not_spam(self):
        return self.filter(is_spam=False)

    def spam(self):
        return self.filter(is_spam=True)

    def category_counts(self):
        """Anzahl je Anfrageart, damit die Uebersicht "wie viele von X" zeigen kann."""
        rows = self.values("category").annotate(total=models.Count("id"))
        return {row["category"]: row["total"] for row in rows}


class Notification(models.Model):
    class Priority(models.TextChoices):
        LOW = "low", "Niedrig"
        NORMAL = "normal", "Normal"
        HIGH = "high", "Hoch"

    class Category(models.TextChoices):
        """Woher die Benachrichtigung stammt.

        Die ersten drei Werte entsprechen ``Message.Category``. Die Art wird beim
        Anlegen mitgeschrieben statt ueber ``message__category`` gelesen, damit
        Filter und Zaehlungen ohne Join auskommen und die Zuordnung erhalten
        bleibt, wenn die verknuepfte Anfrage spaeter geloescht wird.
        """

        GENERAL = "general", "Allgemeine Anfrage"
        MEMBERSHIP = "membership", "Mitgliedschaft"
        REPAIR = "repair", "Reparaturservice"
        ORDER = "order", "Bestellung"
        SYSTEM = "system", "Hinweis"

    # Anfragearten in der Reihenfolge, in der sie im CMS als Filter erscheinen.
    CONTACT_CATEGORIES = (Category.GENERAL, Category.MEMBERSHIP, Category.REPAIR)

    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, default="")
    priority = models.CharField(
        max_length=10,
        choices=Priority.choices,
        default=Priority.NORMAL,
    )
    seen = models.BooleanField(default=False)
    category = models.CharField(
        max_length=20,
        choices=Category.choices,
        default=Category.SYSTEM,
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    is_spam = models.BooleanField(default=False)
    message = models.ForeignKey(
        Message,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="notifications",
    )
    order = models.ForeignKey(
        Order,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="notifications",
    )
    link_url = models.URLField(blank=True, default="")

    objects = NotificationQuerySet.as_manager()

    class Meta:
        db_table = "ycms_notification"
        indexes = [
            models.Index(fields=["seen"], name="ycms_notifi_seen_cd2d30_idx"),
            models.Index(fields=["created_at"], name="ycms_notifi_created_99aec2_idx"),
            models.Index(fields=["is_spam"], name="ycms_notifi_is_spam_198dcc_idx"),
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"[{self.get_priority_display()}] {self.title}"

    def get_absolute_url(self):
        return reverse("cms:notification-detail", args=[self.pk])

    @property
    def has_target(self) -> bool:
        return bool(self.message_id or self.link_url)

    @property
    def external_target_url(self) -> str:
        return self.link_url or ""

    @property
    def is_contact_request(self) -> bool:
        return self.category in self.CONTACT_CATEGORIES

    @property
    def category_meta(self) -> dict:
        """Symbol, Farbton und Kurzbezeichnung fuer die Darstellung im CMS."""
        if self.category in CONTACT_CATEGORY_META:
            return CONTACT_CATEGORY_META[self.category]
        if self.category == self.Category.ORDER:
            return {"label": "Bestellung", "short": "Bestellung", "icon": "bi-bag-fill", "tone": "violet"}
        return {"label": "Hinweis", "short": "Hinweis", "icon": "bi-bell-fill", "tone": "slate"}
