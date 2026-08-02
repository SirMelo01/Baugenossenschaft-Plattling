from django.conf import settings
from django.core.mail import send_mail

from yoolink.ycms.models import UserSettings

from .models import Order


def get_public_user_settings():
    """Return the public shop profile used for outgoing mails."""
    return UserSettings.objects.filter(user__is_staff=False).first()


def build_order_summary(order):
    """Build a reusable order summary block."""
    lines = []

    for item in order.items.select_related("product").all():
        lines.append(f"{item.quantity}x {item.product.title} - {item.subtotal():.2f} Euro")

    lines.append("------------------------------------------")
    lines.append(f"Nettopreis: {order.total_net():.2f} Euro")
    lines.append(f"Lieferung: {order.shipping_price():.2f} Euro")
    lines.append(f"Umsatzsteuer (19%): {order.calculate_tax():.2f} Euro")
    lines.append("------------------------------------------")
    lines.append(f"Gesamtpreis: {order.total():.2f} Euro")

    return "\n".join(lines)


def build_contact_footer(user_settings):
    """Build the standard footer used in shop mails."""
    if not user_settings:
        return "\n\nUnterstützt durch YooLink\nhttps://yoolink.de"

    lines = [
        "",
        "Mit freundlichen Grüßen,",
        user_settings.full_name or "",
    ]

    if user_settings.company_name:
        lines.append(user_settings.company_name)

    if user_settings.tel_number and user_settings.tel_number != "0":
        lines.append(f"Tel. {user_settings.tel_number}")

    if user_settings.fax_number and user_settings.fax_number != "0":
        lines.append(f"Fax {user_settings.fax_number}")

    if user_settings.mobile_number and user_settings.mobile_number != "0":
        lines.append(f"Handy {user_settings.mobile_number}")

    if user_settings.email:
        lines.append(user_settings.email)

    if user_settings.website:
        lines.append(user_settings.website)

    lines.extend([
        "",
        "Unterstützt durch YooLink",
        "https://yoolink.de",
    ])

    return "\n".join(lines)


def send_shop_mail(subject, message, recipient_list):
    """Send a plain text shop mail."""
    send_mail(
        subject,
        message,
        settings.EMAIL_HOST_USER,
        recipient_list,
        fail_silently=False,
    )


def send_payment_confirmation(order: Order):
    """Send payment confirmation to the buyer."""
    if not order.buyer_email:
        return

    user_settings = get_public_user_settings()
    if not user_settings:
        return

    subject = f"Ihr Auftrag {order.id} wurde bezahlt"

    lines = [
        f"Vielen Dank. Ihr Auftrag mit der Auftragsnummer #{order.id} wurde erfolgreich bezahlt.",
    ]

    if order.shipping == "SHIPPING":
        lines.append("Die Produkte werden in Kürze an Sie versandt.")
        lines.append("Sie erhalten eine weitere E Mail, sobald die Ware verschickt wird.")
    elif order.shipping == "PICKUP":
        lines.append("Die Produkte werden bereitgestellt.")
        lines.append("Sie erhalten in Kürze eine E Mail, sobald Sie die Ware abholen können.")

    lines.extend([
        "",
        "Details Ihres Auftrags",
        "",
        build_order_summary(order),
        "",
        f"Ihre ausgewählte Liefermethode: {order.get_shipping_display()}",
    ])

    if order.buyer_address:
        if order.shipping == "SHIPPING":
            lines.append(f"Versandadresse: {order.buyer_address.get_shipping_address()}")
        elif order.shipping == "PICKUP":
            lines.append(f"Rechnungsadresse: {order.buyer_address.get_shipping_address()}")

    lines.append(f"Ihre ausgewählte Bezahlmethode: {order.get_payment_display()}")
    lines.append("")
    lines.append("Vielen Dank für Ihr Vertrauen.")
    lines.append(build_contact_footer(user_settings))

    message = "\n".join(lines)
    send_shop_mail(subject, message, [order.buyer_email])


def send_ready_for_pickup_confirmation(order: Order):
    """Send pickup ready confirmation to the buyer."""
    if not order.buyer_email:
        return

    user_settings = get_public_user_settings()
    if not user_settings:
        return

    subject = f"Ihr Auftrag {order.id} ist bereit zur Abholung"

    lines = [
        f"Ihr Auftrag mit der Auftragsnummer #{order.id} ist bereit zur Abholung.",
        "Die Produkte können während der Öffnungszeiten abgeholt werden.",
        "",
        "Vielen Dank für Ihre Bestellung und bis bald.",
        build_contact_footer(user_settings),
    ]

    message = "\n".join(lines)
    send_shop_mail(subject, message, [order.buyer_email])


def send_shipping_confirmation(order: Order):
    """Send shipping confirmation to the buyer."""
    if not order.buyer_email:
        return

    user_settings = get_public_user_settings()
    if not user_settings:
        return

    subject = "Ihre Produkte sind auf dem Weg"

    lines = [
        f"Ihre Produkte aus dem Auftrag #{order.id} sind auf dem Weg zu Ihnen.",
        "Vielen Dank für Ihren Einkauf.",
        "",
        "Details Ihres Auftrags",
        "",
        build_order_summary(order),
    ]

    if order.buyer_address:
        lines.extend([
            "",
            f"Versandadresse: {order.buyer_address.get_shipping_address()}",
        ])

    lines.extend([
        "",
        "Wir informieren Sie, wenn die Produkte unterwegs sind. Vielen Dank.",
        build_contact_footer(user_settings),
    ])

    message = "\n".join(lines)
    send_shop_mail(subject, message, [order.buyer_email])