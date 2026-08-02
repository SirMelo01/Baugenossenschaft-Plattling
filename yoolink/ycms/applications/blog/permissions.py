from rest_framework.permissions import SAFE_METHODS, BasePermission

from yoolink.ycms.models import DeveloperApiKey


class HasDeveloperApiKeyScope(BasePermission):
    message = "Dieser API-Key hat keine Berechtigung für diese Aktion."

    def has_permission(self, request, view):
        api_key = request.auth
        if not isinstance(api_key, DeveloperApiKey):
            return False

        app_code = getattr(view, "api_app_code", None)
        if app_code and not api_key.allows_app(app_code):
            return False

        if request.method not in SAFE_METHODS and not api_key.allows_write():
            return False

        return api_key.is_usable()
