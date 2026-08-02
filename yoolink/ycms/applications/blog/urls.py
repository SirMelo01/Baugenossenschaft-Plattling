from rest_framework.routers import SimpleRouter

from .views import ExternalBlogViewSet


app_name = "ycms_blog_api"

router = SimpleRouter()
router.register("blog", ExternalBlogViewSet, basename="external-blog")

urlpatterns = router.urls
