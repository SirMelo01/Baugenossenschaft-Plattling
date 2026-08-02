from functools import wraps

from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse

from yoolink.ycms.models import CMS_PERMISSION_CHOICES, SYSTEM_ROLE_DEFAULTS, CMSRole


PERMISSION_LABELS = dict(CMS_PERMISSION_CHOICES)


def ensure_system_roles():
    roles = {}
    for slug, defaults in SYSTEM_ROLE_DEFAULTS.items():
        role, _created = CMSRole.objects.update_or_create(
            slug=slug,
            defaults={
                "name": defaults["name"],
                "permissions": defaults["permissions"],
                "is_system": True,
            },
        )
        roles[slug] = role
    return roles


def user_permissions(user):
    if not user or not user.is_authenticated:
        return set()

    if user.is_superuser:
        return {code for code, _label in CMS_PERMISSION_CHOICES}

    permissions = set()
    assignments = (
        user.cms_role_assignments
        .select_related("role")
        .only("role__permissions")
    )
    for assignment in assignments:
        permissions.update(assignment.role.permissions or [])
        if assignment.role.slug in SYSTEM_ROLE_DEFAULTS:
            permissions.update(SYSTEM_ROLE_DEFAULTS[assignment.role.slug]["permissions"])
    return permissions


def has_cms_permission(user, permission):
    return permission in user_permissions(user)


def has_any_cms_permission(user, permissions):
    current = user_permissions(user)
    return any(permission in current for permission in permissions)


def cms_permission_required(permission):
    def decorator(view_func):
        @wraps(view_func)
        def wrapped(request, *args, **kwargs):
            if has_cms_permission(request.user, permission):
                return view_func(request, *args, **kwargs)

            messages.error(request, "Du hast für diesen CMS-Bereich keine Berechtigung.")
            return redirect(reverse("ycms:cms"))

        return wrapped

    return decorator
