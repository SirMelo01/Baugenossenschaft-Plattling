from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .models import Notification


@login_required
def notifications_list(request):
    qs = Notification.objects.latest_first().not_spam()

    status = request.GET.get("status", "all")
    priority = request.GET.get("priority", "all")
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

    paginator = Paginator(qs, per_page)
    page_obj = paginator.get_page(request.GET.get("page", 1))

    preserved = request.GET.copy()
    preserved.pop("page", None)

    return render(
        request,
        "pages/cms/notifications/notifications_list.html",
        {
            "notifications": page_obj.object_list,
            "page_obj": page_obj,
            "paginator": paginator,
            "querystring": preserved.urlencode(),
            "filter_status": status,
            "filter_priority": priority,
            "per_page": per_page,
            "unread_count": Notification.objects.unread().count(),
            "total_count": Notification.objects.not_spam().count(),
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

