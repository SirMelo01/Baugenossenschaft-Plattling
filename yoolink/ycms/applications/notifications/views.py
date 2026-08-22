from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import FileResponse, Http404, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from yoolink.ycms.models import MessageAttachment

from .models import Notification


def _category_summary(base_qs, active_category):
    """Zaehlt je Anfrageart Gesamt und Ungelesen fuer die Filterleiste.

    Die Zahlen beziehen sich immer auf den kompletten Posteingang, nicht auf die
    gerade gefilterte Ansicht - sonst zeigte der Filter, nach dem gerade gefiltert
    wird, als einziger noch seine echte Zahl.
    """
    totals = base_qs.category_counts()
    unread = base_qs.filter(seen=False).category_counts()

    summary = []
    for category in Notification.Category.values:
        meta = Notification(category=category).category_meta
        summary.append({
            "value": category,
            "label": meta["label"],
            "short": meta["short"],
            "icon": meta["icon"],
            "tone": meta["tone"],
            "count": totals.get(category, 0),
            "unread": unread.get(category, 0),
            "is_active": active_category == category,
            "is_contact": category in Notification.CONTACT_CATEGORIES,
        })
    return summary


@login_required
def notifications_list(request):
    inbox = Notification.objects.not_spam()
    qs = inbox.latest_first()

    status = request.GET.get("status", "all")
    priority = request.GET.get("priority", "all")
    category = request.GET.get("category", "all")
    per_page = request.GET.get("per_page", "10")

    try:
        per_page = max(1, min(100, int(per_page)))
    except ValueError:
        per_page = 10

    if status == "open":
        qs = qs.filter(seen=False)
    elif status == "closed":
        qs = qs.filter(seen=True)

    if priority in {"low", "normal", "high"}:
        qs = qs.filter(priority=priority)

    if category in Notification.Category.values:
        qs = qs.filter(category=category)
    else:
        category = "all"

    paginator = Paginator(qs, per_page)
    page_obj = paginator.get_page(request.GET.get("page", 1))

    preserved = request.GET.copy()
    preserved.pop("page", None)

    # Querystring ohne "category", damit die Filterchips den restlichen Filter
    # (Status, Prioritaet, Seitengroesse) beibehalten.
    without_category = request.GET.copy()
    without_category.pop("page", None)
    without_category.pop("category", None)

    return render(
        request,
        "pages/cms/notifications/notifications_list.html",
        {
            "notifications": page_obj.object_list,
            "page_obj": page_obj,
            "paginator": paginator,
            "querystring": preserved.urlencode(),
            "category_querystring": without_category.urlencode(),
            "filter_status": status,
            "filter_priority": priority,
            "filter_category": category,
            "category_summary": _category_summary(inbox, category),
            "filtered_count": paginator.count,
            "per_page": per_page,
            "unread_count": Notification.objects.unread().count(),
            "total_count": inbox.count(),
            "spam_count": Notification.objects.spam().count(),
        },
    )


@login_required
def notifications_mark_all_read(request):
    if request.method != "POST":
        return HttpResponseForbidden()
    Notification.objects.unread().update(seen=True)
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({"ok": True})
    return redirect("cms:notifications-list")


@login_required
def notification_mark_read(request, pk):
    if request.method != "POST":
        return HttpResponseForbidden()
    notification = get_object_or_404(Notification, pk=pk)
    notification.seen = True
    notification.save(update_fields=["seen"])
    return JsonResponse({"ok": True})


@login_required
def notification_detail(request, pk):
    notification = get_object_or_404(Notification, pk=pk)

    if not notification.seen:
        notification.seen = True
        notification.save(update_fields=["seen"])

    return render(
        request,
        "pages/cms/notifications/notification_detail.html",
        {"notification": notification},
    )


@login_required
@require_POST
def notification_delete(request, pk):
    notification = get_object_or_404(Notification, pk=pk)
    notification.delete()
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({"ok": True})
    return redirect("cms:notifications-list")


@login_required
@require_POST
def notification_mark_spam(request, pk):
    notification = get_object_or_404(Notification, pk=pk)
    notification.is_spam = True
    notification.seen = True
    notification.save(update_fields=["is_spam", "seen"])

    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({"ok": True})
    return redirect("cms:notifications-list")


@login_required
def notifications_spam_list(request):
    qs = Notification.objects.spam().latest_first()

    per_page = request.GET.get("per_page", "20")
    try:
        per_page = max(1, min(100, int(per_page)))
    except ValueError:
        per_page = 20

    paginator = Paginator(qs, per_page)
    page_obj = paginator.get_page(request.GET.get("page", 1))

    preserved = request.GET.copy()
    preserved.pop("page", None)

    return render(
        request,
        "pages/cms/notifications/notifications_spam_list.html",
        {
            "notifications": page_obj.object_list,
            "page_obj": page_obj,
            "paginator": paginator,
            "querystring": preserved.urlencode(),
            "per_page": per_page,
            "spam_count": paginator.count,
            "inbox_count": Notification.objects.not_spam().count(),
        },
    )


@login_required
@require_POST
def notifications_spam_delete_all(request):
    Notification.objects.spam().delete()
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({"ok": True})
    return redirect("cms:notifications-spam-list")


@login_required
@require_POST
def notification_mark_ham(request, pk):
    notification = get_object_or_404(Notification, pk=pk)
    notification.is_spam = False
    notification.save(update_fields=["is_spam"])

    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({"ok": True})
    return redirect("cms:notifications-spam-list")


@login_required
def message_attachment(request, pk):
    """Einen Anhang einer Kontaktanfrage ausliefern.

    Anhaenge liegen in der privaten Ablage und haben bewusst keine oeffentliche
    Adresse - hier steckt zum Beispiel eine ausgefuellte Selbstauskunft drin.
    Ausgeliefert wird deshalb nur an angemeldete Personen, und der Inhaltstyp
    kommt aus unserer eigenen Pruefung beim Hochladen, nicht aus der Datei.

    Bilder duerfen eingebettet angezeigt werden: sie wurden beim Hochladen von
    Pillow neu geschrieben und sind damit garantiert Bilder. Alles andere geht
    ausschliesslich als Download raus.
    """
    attachment = get_object_or_404(MessageAttachment.objects.select_related("message"), pk=pk)

    try:
        handle = attachment.file.open("rb")
    except (FileNotFoundError, ValueError, OSError):
        raise Http404("Die Datei ist nicht mehr vorhanden.")

    response = FileResponse(
        handle,
        content_type=attachment.content_type or "application/octet-stream",
        as_attachment=not attachment.is_image,
        filename=attachment.original_name or f"anhang-{attachment.pk}",
    )
    # Der Browser soll den Inhaltstyp nicht selbst erraten duerfen.
    response["X-Content-Type-Options"] = "nosniff"
    response["Referrer-Policy"] = "no-referrer"
    # Personenbezogene Anhaenge gehoeren in keinen Zwischenspeicher.
    response["Cache-Control"] = "private, no-store"
    return response
