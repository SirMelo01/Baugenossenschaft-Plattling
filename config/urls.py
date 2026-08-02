from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.views import defaults as default_views
from django.views.generic import TemplateView
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework.authtoken.views import obtain_auth_token
from yoolink.views import load_index, kontaktform, load_kunden, load_kunde_detail, load_cmsinfo, load_logos, load_visitenkarte, load_medien, load_webdesign, load_webdesign_deggendorf, datenschutz_view, cookies_view, leistungen_view, impressum_view
from django.views.generic import RedirectView
from django.contrib.staticfiles.storage import staticfiles_storage
from django.urls import path, include

from django.contrib.sitemaps.views import sitemap
from yoolink.sitemaps import StaticViewSitemap, BlogSitemap, CustomerSitemap, ProductSitemap

from yoolink.ycms.applications.shop.views import cart_verify_success_view, cart_view, order_verify_success_view, order_verify_view

sitemaps = {
    'static': StaticViewSitemap,
    'blog': BlogSitemap,
    'product': ProductSitemap,
    'customer': CustomerSitemap,
}

from django.conf.urls.i18n import i18n_patterns, set_language

urlpatterns = [
    # Admin und API können gerne ohne Sprachprefix bleiben
    path(settings.ADMIN_URL, admin.site.urls),
    path("api/", include("config.api_router")),
    path("auth-token/", obtain_auth_token),
    path("api/schema/", SpectacularAPIView.as_view(), name="api-schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="api-schema"), name="api-docs"),
    path('i18n/setlang/', set_language, name='set_language'),
    path(
        "robots.txt",
        TemplateView.as_view(template_name="robots.txt", content_type="text/plain"),
        name="robots",
    ),
    path("cms/", include("yoolink.ycms.urls", namespace="ycms")),
    path('cart/', cart_view, name='cart-view'),
    path('cart/success/', cart_verify_success_view, name='cart-verify-success-view'),
    path('order/verify/', order_verify_view, name='order-verify'),
    path('order/success/', order_verify_success_view, name='order-verify-success-view'),
    path("shop/", include("yoolink.ycms.applications.shop.public_urls")),
    path("", include('django.contrib.auth.urls')),
]

urlpatterns += i18n_patterns(
    path("", view=load_index, name="home"),
    path('sitemap.xml', sitemap, {'sitemaps': sitemaps}, name="django.contrib.sitemaps.views.sitemap"),
    path("impressum/", view=impressum_view, name="impressum"),
    path("kontakt/", view=kontaktform, name="kontakt"),
    path("datenschutz/", view=datenschutz_view, name="datenschutz"),
    path("cookies/", view=cookies_view, name="cookies"),
    path("leistungen/cms/", view=load_cmsinfo, name="leistungen_cms"),
    path("leistungen/logos/", view=load_logos, name="leistungen_logos"),
    path("leistungen/visitenkarte/", view=load_visitenkarte, name="leistungen_visitenkarte"),
    path("leistungen/medien/", view=load_medien, name="leistungen_medien"),
    path("leistungen/webdesign/", view=load_webdesign, name="leistungen_webdesign"),
    path("webdesign-deggendorf/", view=load_webdesign_deggendorf, name="webdesign_deggendorf"),
    path("blog/", include("yoolink.blog.urls", namespace="blog")),
    path("users/", include("yoolink.users.urls", namespace="users")),
    path("kunden/", view=load_kunden, name="kunden"),
    path("kunden/<slug:slug>/", view=load_kunde_detail, name="kunde-detail"),
    path("leistungen/", view=leistungen_view, name="leistungen"),
    path("products/", include("yoolink.ycms.applications.shop.public_product_urls")),
    prefix_default_language=False,
)



if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    # This allows the error pages to be debugged during development, just visit
    # these url in browser to see how these error pages look like.
    urlpatterns += [
        path(
            "400/",
            default_views.bad_request,
            kwargs={"exception": Exception("Bad Request!")},
        ),
        path(
            "403/",
            default_views.permission_denied,
            kwargs={"exception": Exception("Permission Denied")},
        ),
        path(
            "404/",
            default_views.page_not_found,
            kwargs={"exception": Exception("Page not Found")},
        ),
        path("500/", default_views.server_error),
    ]
    if "debug_toolbar" in settings.INSTALLED_APPS:
        import debug_toolbar

        urlpatterns = [path("__debug__/", include(debug_toolbar.urls))] + urlpatterns
