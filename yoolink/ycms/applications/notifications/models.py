from django.db import models
from django.urls import reverse

from yoolink.ycms.applications.shop.models import Order
from yoolink.ycms.models import Message


class NotificationQuerySet(models.QuerySet):
    def unread(self):
        return self.filter(seen=False, is_spam=False)

    def latest_first(self):
        return self.order_by("-created_at")

    def not_spam(self):
        return self.filter(is_spam=False)

    def spam(self):
        return self.filter(is_spam=True)


class Notification(models.Model):
    class Priority(models.TextChoices):
        LOW = "low", "Niedrig"
        NORMAL = "normal", "Normal"
        HIGH = "high", "Hoch"

    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, default="")
    priority = models.CharField(
        max_length=10,
        choices=Priority.choices,
        default=Priority.NORMAL,
    )
    seen = models.BooleanField(default=False)
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

