# myapp/middleware.py
from django.conf import settings
from django.http import HttpResponsePermanentRedirect


class WwwRedirectMiddleware:
    """Leitet www.<domain> per 301 auf die kanonische Domain um.

    Domain kommt aus settings.SITE_DOMAIN, damit sie nur an einer Stelle gepflegt
    wird. Der Redirect behält den Querystring bei.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        host = request.get_host().partition(":")[0]
        if host == f"www.{settings.SITE_DOMAIN}":
            return HttpResponsePermanentRedirect(
                f"{settings.SITE_BASE_URL}{request.get_full_path()}"
            )
        return self.get_response(request)
