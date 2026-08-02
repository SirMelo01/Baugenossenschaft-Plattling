from django.conf import settings
from django.urls import include, path
from rest_framework.routers import DefaultRouter, SimpleRouter

from yoolink.users.api.views import UserViewSet
from yoolink.ycms.applications.blog.views import ExternalApiPingView, ExternalConnectTokenView

if settings.DEBUG:
    router = DefaultRouter()
else:
    router = SimpleRouter()

router.register("users", UserViewSet)


app_name = "api"
urlpatterns = router.urls + [
    path("connect/token/", ExternalConnectTokenView.as_view(), name="developer-connect-token"),
    path("ping/", ExternalApiPingView.as_view(), name="developer-ping"),
    path("cms/", include("yoolink.ycms.applications.blog.urls")),
]
