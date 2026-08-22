from django.db.models.signals import post_save
from django.dispatch import receiver
from django.urls import reverse

from yoolink.ycms.applications.shop.models import Order
from yoolink.ycms.models import Message, contact_category_meta
from yoolink.ycms.spam_detection import is_spam_message

from .models import Notification


@receiver(post_save, sender=Message)
def create_notification_for_message(sender, instance: Message, created, **kwargs):
    if not created:
        return

    spam_flag = is_spam_message(instance)
    meta = contact_category_meta(instance.category)

    # Die Art der Anfrage steht im Titel, damit im Postfach ohne Klick erkennbar
    # ist, worum es geht; ``category`` traegt dieselbe Information maschinenlesbar
    # fuer Filter und Zaehlung.
    Notification.objects.create(
        title=meta["notification_title"] if not spam_flag else f"Möglicher Spam ({meta['label']})",
        description=(instance.title or instance.message[:120]),
        priority=Notification.Priority.NORMAL if not spam_flag else Notification.Priority.LOW,
        category=instance.category,
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
        f"Kunde: {buyer or '-'}  •  E-Mail: {email}\n"
        f"Positionen: {total_qty}  •  Gesamt: {total_sum} €  •  Status: {instance.get_status_display()}"
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
        category=Notification.Category.ORDER,
        order=instance,
        link_url=reverse("cms:order-detail-view", args=[instance.pk]),
    )
