from django.conf import settings

from yoolink.ycms.views import get_active_language
from yoolink.ycms.applications.notifications.models import Notification
from .models import CMS_PERMISSION_CHOICES, WebsiteSettings
from .permissions import user_permissions
from .seo_schema import build_site_schema_jsonld

def user_settings_context(request):
    # Kanonische Basis-URL der Seite (aus settings.SITE_DOMAIN). Dient in den
    # Templates als Fallback für canonical-/OG-URLs, wenn im CMS keine Website
    # hinterlegt ist.
    context = {'site_base_url': settings.SITE_BASE_URL}
    owner_data = WebsiteSettings.get_site_owner()
    if owner_data:
        context['owner_data'] = owner_data
        context['website_settings'] = owner_data
    # Site-wide Organization/WebSite/LocalBusiness JSON-LD, built from the CMS
    # owner record (with safe fallbacks). Rendered once in base.html.
    try:
        context['site_schema_jsonld'] = build_site_schema_jsonld(
            owner_data, base_url=settings.SITE_BASE_URL
        )
    except Exception:
        context['site_schema_jsonld'] = ""
    return context


def bgp_shell_context(request):
    """Shared shell data for templates that inherit base.html.

    The Baugenossenschaft shell used to live only in the BGP demo base. Public
    pages such as blog, impressum and datenschutz inherit base.html directly, so
    they need the same BGP context without every view wiring it by hand.
    """
    path = getattr(request, "path_info", request.path)
    is_demo_preview = path.startswith("/cms/demos/")

    if path.startswith("/cms/") and not is_demo_preview:
        return {}

    admin_prefix = "/" + settings.ADMIN_URL.strip("/") + "/"
    if (
        path.startswith(admin_prefix)
        or path.startswith("/api/")
        or path.startswith("/auth-token/")
    ):
        return {}

    from yoolink.ycms.applications.content.bgp_content import bgp_content_context

    context = bgp_content_context()
    context["bgp_is_public"] = not is_demo_preview
    return context


def cms_permissions_context(request):
    if not request.user.is_authenticated:
        return {}

    permissions = user_permissions(request.user)
    return {
        "cms_permissions": permissions,
        "cms_permission_labels": dict(CMS_PERMISSION_CHOICES),
        "can_manage_users": "users.manage" in permissions,
        "can_manage_roles": "roles.manage" in permissions,
    }

def notifications_context(request):
    unread_qs = Notification.objects.unread().latest_first()
    unread_count = unread_qs.count()

    limit = 8
    latest_unread = list(unread_qs[:limit])
    overflow = max(unread_count - limit, 0)

    return {
        'nav_unread_notifications_count': unread_count,        # Zahl fürs Badge
        'nav_latest_unread_notifications': latest_unread,      # Dropdown-Liste (nur ungelesen)
        'nav_unread_overflow': overflow,                       # „…und X weitere“
        'nav_unread_limit': limit,
    }

def cms_language_context(request):
    if not request.path.startswith('/cms/'):
        return {}
    
    return {
        "cms_language": get_active_language(request)
    }

def matomo_context(request):
    # Exposes the Matomo config to templates. matomo_enabled is False in DEBUG
    # (local/dev), so base.html never emits the tracking snippet outside production.
    return {
        "matomo_url": settings.MATOMO_URL,
        "matomo_site_id": settings.MATOMO_SITE_ID,
        "matomo_enabled": settings.MATOMO_ENABLED,
    }
