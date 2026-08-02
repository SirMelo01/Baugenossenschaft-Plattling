from django.urls import path

from . import views
from yoolink.ycms.permissions import cms_permission_required

pages_required = cms_permission_required("pages.edit")

urlpatterns = [
    path("", pages_required(views.content_view), name="sites"),
    path("save/", pages_required(views.save_text_content), name="save_text_content"),
    path("hauptseite/", pages_required(views.site_view_main), name="site_hauptseite"),
    path("hauptseite/Hero/", pages_required(views.site_view_main_hero), name="site_hauptseite_hero"),
    path("hauptseite/Reponsive/", pages_required(views.site_view_main_responsive), name="site_hauptseite_responsive"),
    path("hauptseite/CMS/", pages_required(views.site_view_main_cms), name="site_hauptseite_cms"),
    path("hauptseite/Preis/", pages_required(views.site_view_main_price), name="site_hauptseite_price"),
    path("hauptseite/Team/", pages_required(views.site_view_main_team), name="site_hauptseite_team"),
    path("hauptseite/Know-How/", pages_required(views.site_view_main_know_how), name="site_hauptseite_know_how"),
    path("hauptseite/kunden/", pages_required(views.site_view_main_kunden), name="site_hauptseite_kunden"),
    path("hauptseite/FAQ/", pages_required(views.site_view_main_faq), name="site_hauptseite_faq"),
    path("kunden/", pages_required(views.site_view_kunden), name="site_kunden"),
    path("kunden/customers/", pages_required(views.customer_list_view), name="customer-list"),
    path("kunden/customers/create/", pages_required(views.customer_create_view), name="customer-create"),
    path("kunden/customers/reorder/", pages_required(views.customer_reorder_view), name="customer-reorder"),
    path("kunden/customers/<int:pk>/edit/", pages_required(views.customer_edit_view), name="customer-edit"),
    path("kunden/customers/<int:pk>/delete/", pages_required(views.customer_delete_view), name="customer-delete"),
    path("leistungen/", pages_required(views.site_view_leistungen), name="site_leistungen"),
    path("leistungen/cms/", pages_required(views.site_view_cmsinfo), name="site_leistungen_cms"),
    path("leistungen/logos/", pages_required(views.site_view_logos), name="site_leistungen_logos"),
    path("leistungen/webdesign/", pages_required(views.site_view_webdesign), name="site_leistungen_webdesign"),
    path("leistungen/visitenkarte/", pages_required(views.site_view_visitenkarte), name="site_leistungen_visitenkarte"),
    path("leistungen/medien/", pages_required(views.site_view_medien), name="site_leistungen_medien"),
    path("webdesign-deggendorf/", pages_required(views.site_view_webdesign_deggendorf), name="site_webdesign_deggendorf"),
    path("standorte/", pages_required(views.location_list_view), name="location-list"),
    path("standorte/create/", pages_required(views.location_create_view), name="location-create"),
    path("standorte/reorder/", pages_required(views.location_reorder_view), name="location-reorder"),
    path("standorte/<int:pk>/edit/", pages_required(views.location_edit_view), name="location-edit"),
    path("standorte/<int:pk>/delete/", pages_required(views.location_delete_view), name="location-delete"),
    path("datenschutz/", pages_required(views.site_view_datenschutz), name="site_datenschutz"),
    path("datenschutz/save/", pages_required(views.save_privacy_policy), name="save_privacy_policy"),
    path("impressum/", pages_required(views.site_view_impressum), name="site_impressum"),
    path("impressum/save/", pages_required(views.save_impressum), name="save_impressum"),
    path("cookies/", pages_required(views.site_view_cookies), name="site_cookies"),
    path("kontakt/", pages_required(views.site_view_kontakt), name="site_kontakt"),
    path("blog-uebersicht/", pages_required(views.site_view_blog_overview), name="site_blog_overview"),
]
