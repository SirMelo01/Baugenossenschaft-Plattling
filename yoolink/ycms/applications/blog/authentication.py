import secrets

from django.utils import timezone
from rest_framework.authentication import BaseAuthentication, get_authorization_header
from rest_framework.exceptions import AuthenticationFailed

from yoolink.ycms.models import DeveloperApiKey


class DeveloperApiKeyAuthentication(BaseAuthentication):
    """
    Authentifiziert externe Automationen mit YooLink Developer API Keys.

    Unterstützt:
    - Authorization: Bearer <key>
    - X-YooLink-API-Key: <key>
    """

    keyword = "Bearer"

    def authenticate(self, request):
        raw_key = self._get_raw_key(request)
        if not raw_key:
            return None

        prefix = DeveloperApiKey.extract_prefix(raw_key)
        if not prefix:
            raise AuthenticationFailed("Ungültiger API-Key.")

        try:
            api_key = DeveloperApiKey.objects.select_related("created_by").get(prefix=prefix)
        except DeveloperApiKey.DoesNotExist as exc:
            raise AuthenticationFailed("Ungültiger API-Key.") from exc

        expected_hash = DeveloperApiKey.make_key_hash(raw_key)
        if not secrets.compare_digest(api_key.key_hash, expected_hash):
            raise AuthenticationFailed("Ungültiger API-Key.")

        if not api_key.is_usable():
            raise AuthenticationFailed("Dieser API-Key ist abgelaufen oder wurde widerrufen.")

        if not api_key.created_by.is_active:
            raise AuthenticationFailed("Der Benutzer dieses API-Keys ist deaktiviert.")

        now = timezone.now()
        DeveloperApiKey.objects.filter(pk=api_key.pk).update(last_used_at=now)
        api_key.last_used_at = now

        return (api_key.created_by, api_key)

    def authenticate_header(self, request):
        return f'{self.keyword} realm="yoolink-api"'

    def _get_raw_key(self, request):
        auth_header = get_authorization_header(request).decode("utf-8")
        if auth_header:
            parts = auth_header.split()
            if len(parts) == 2 and parts[0].lower() == self.keyword.lower():
                return parts[1].strip()

        return (request.META.get("HTTP_X_YOOLINK_API_KEY") or "").strip()
