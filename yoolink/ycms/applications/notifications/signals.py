from django.db.models.signals import post_save
from django.dispatch import receiver
from django.urls import reverse

from yoolink.ycms.applications.shop.models import Order
from yoolink.ycms.models import Message
from yoolink.ycms.spam_detection import is_spam_message

from .models import Notification


@receiver(post_save, sender=Message)
def create_notification_for_message(sender, instance: Message, created, **kwargs):
    if not created:
        return

    spam_flag = is_spam_message(instance)

    Notification.objects.create(
        title="Neue Kontaktanfrage" if not spam_flag else "MÃ¶glicher Spam (Kontaktformular)",
        description=(instance.title or instance.message[:120]),
        priority=Notification.Priority.NORMAL if not spam_flag else Notification.Priority.LOW,
        message=instance,
        link_url="",
        is_spam=spam_flag,
    )


@receiver(post_save, sender=Order)
def create_notification_for_order(sender, instance: Order, created, **kwargs):
    if not created:
        return

    total_qty = instance.total_quantity()
    total_sum = instance.total()
    buyer = getattr(instance.buyer_address, "get_buyer_name", lambda: "")()
    email = instance.buyer_email

    title = f"Neue Bestellung #{instance.pk}"
    description = (
        f"Kunde: {buyer or '-'}  â€¢  E-Mail: {email}\n"
        f"Positionen: {total_qty}  â€¢  Gesamt: {total_sum} â‚¬  â€¢  Status: {instance.get_status_display()}"
    )
    priority = (
        Notification.Priority.HIGH
        if instance.paid or instance.status in ("PAID",)
        else Notification.Priority.NORMAL
    )

    Notification.objects.create(
        title=title,
        description=description,
        priority=priority,
        order=instance,
        link_url=reverse("cms:order-detail-view", args=[instance.pk]),
    )
