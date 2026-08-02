import json
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.db.models import Max
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils.translation import activate, get_language_from_request
from django.views.decorators.http import require_http_methods

from yoolink.ycms.models import FAQ, Button, Galerie, PageLink, PricingCard, TeamMember, UserSettings, VideoFile, WebsiteSettings, fileentry

from .models import Customer, ImpressumBlock, PrivacyPolicy, ServiceLocation, TextContent

DEFAULT_LANGUAGE = "en"


def get_active_language(request):
    lang = get_language_from_request(request)
    available_languages = dict(settings.LANGUAGES)

    if lang not in available_languages:
        lang = DEFAULT_LANGUAGE

    activate(lang)
    return lang


def _get_user_settings(user):
    user_settings, _ = UserSettings.objects.get_or_create(
        user=user,
        defaults={"email": user.email or ""},
    )

    if not user_settings.email and user.email:
        user_settings.email = user.email
        user_settings.save(update_fields=["email"])

    return user_settings


def _get_text(name):
    return TextContent.objects.filter(name=name).first()


def _get_image(place):
    return fileentry.objects.filter(place=place).first()


@login_required(login_url="login")
def content_view(request):
    return render(request, "pages/cms/content/content.html", {})


@login_required(login_url="login")
def site_view_main(request):
    """Single combined editor for the whole main page (all sections at once).

    Gathers the same data the individual section views provide so everything can
    be edited on one page. Saving still goes through ``save_text_content`` via the
    generic ``.text-content`` / galery / video markup.
    """
    data = {
        "pricing_count": PricingCard.objects.count(),
        "member_count": TeamMember.objects.count(),
        "faq_count": FAQ.objects.count(),
        "location_count": ServiceLocation.objects.count(),
        # Texts per section
        "hero_text": _get_text("main_hero"),
        "responsive_text": _get_text("main_responsive"),
        "cms_text": _get_text("main_cms"),
        "knowhow_text": _get_text("main_know_how"),
        "kunden_text": _get_text("main_kunden"),
        "standorte_text": _get_text("main_standorte"),
        "price_text": _get_text("main_price"),
        "team_text": _get_text("main_team"),
        "faq_text": _get_text("main_faq"),
    }

    # Know-How cards
    for index in range(1, 4):
        data[f"knowhow_card_{index}"] = _get_text(f"main_know_how_card_{index}")

    # Hero galery
    if Galerie.objects.filter(place="main_hero").exists():
        data["heroImages"] = Galerie.objects.get(place="main_hero").images.all()

    # Responsive galeries
    if Galerie.objects.filter(place="main_responsive_desktop").exists():
        data["responsiveDesktopImages"] = Galerie.objects.get(place="main_responsive_desktop").images.all()
    if Galerie.objects.filter(place="main_responsive_handy").exists():
        data["responsiveHandyImages"] = Galerie.objects.get(place="main_responsive_handy").images.all()

    # CMS video
    if VideoFile.objects.filter(place="main_cms").exists():
        data["cmsVideo"] = VideoFile.objects.get(place="main_cms")

    return render(request, "pages/cms/content/sites/MainSite.html", data)


@login_required(login_url="login")
def site_view_main_hero(request):
    data = {}
    text_content = _get_text("main_hero")
    if text_content:
        data["textContent"] = text_content
    if Galerie.objects.filter(place="main_hero").exists():
        data["heroImages"] = Galerie.objects.get(place="main_hero").images.all()
    return render(request, "pages/cms/content/sites/mainsite/HeroContent.html", data)


@login_required(login_url="login")
def site_view_main_responsive(request):
    data = {}
    text_content = _get_text("main_responsive")
    if text_content:
        data["textContent"] = text_content

    if Galerie.objects.filter(place="main_responsive_desktop").exists():
        data["responsiveDesktopImages"] = Galerie.objects.get(place="main_responsive_desktop").images.all()

    if Galerie.objects.filter(place="main_responsive_handy").exists():
        data["responsiveHandyImages"] = Galerie.objects.get(place="main_responsive_handy").images.all()

    return render(request, "pages/cms/content/sites/mainsite/ResponsiveContent.html", data)


@login_required(login_url="login")
def site_view_main_cms(request):
    data = {}
    text_content = _get_text("main_cms")
    if text_content:
        data["textContent"] = text_content
    if VideoFile.objects.filter(place="main_cms").exists():
        data["cmsVideo"] = VideoFile.objects.get(place="main_cms")
    return render(request, "pages/cms/content/sites/mainsite/CmsContent.html", data)


@login_required(login_url="login")
def site_view_main_price(request):
    data = {"pricing_count": PricingCard.objects.count()}
    text_content = _get_text("main_price")
    if text_content:
        data["textContent"] = text_content
    return render(request, "pages/cms/content/sites/mainsite/PriceContent.html", data)


@login_required(login_url="login")
def site_view_main_team(request):
    data = {"member_count": TeamMember.objects.count()}
    text_content = _get_text("main_team")
    if text_content:
        data["textContent"] = text_content
    return render(request, "pages/cms/content/sites/mainsite/TeamContent.html", data)


@login_required(login_url="login")
def site_view_main_know_how(request):
    data = {}
    text_content = _get_text("main_know_how")
    if text_content:
        data["textContent"] = text_content

    for index in range(1, 4):
        card_content = _get_text(f"main_know_how_card_{index}")
        if card_content:
            data[f"textContentCard{index}"] = card_content

    return render(request, "pages/cms/content/sites/mainsite/KnowHowContent.html", data)


@login_required(login_url="login")
def site_view_main_kunden(request):
    data = {}
    text_content = _get_text("main_kunden")
    if text_content:
        data["textContent"] = text_content
    return render(request, "pages/cms/content/sites/mainsite/KundenContent.html", data)


@login_required(login_url="login")
def site_view_main_faq(request):
    data = {"faq_count": FAQ.objects.count()}
    text_content = _get_text("main_faq")
    if text_content:
        data["textContent"] = text_content
    return render(request, "pages/cms/content/sites/mainsite/FAQContent.html", data)


@login_required(login_url="login")
def site_view_kunden(request):
    data = {}
    text_content = _get_text("main_kunden")
    if text_content:
        data["textContent"] = text_content
    text_content2 = _get_text("main_kunden2")
    if text_content2:
        data["textContent2"] = text_content2
    text_content_references = _get_text("main_kunden_references")
    if text_content_references:
        data["textContentReferences"] = text_content_references
    text_content_bottomcta = _get_text("main_kunden_bottomcta")
    if text_content_bottomcta:
        data["textContentBottomCta"] = text_content_bottomcta
    return render(request, "pages/cms/content/sites/KundenSite.html", data)


@login_required(login_url="login")
def site_view_leistungen(request):
    legacy_logo_image = _get_image("main_leistungen_logos_image")

    return render(
        request,
        "pages/cms/content/sites/LeistungenSite.html",
        {
            "textContent_intro": _get_text("main_leistungen_intro"),
            "textContent_cms": _get_text("main_leistungen_cms"),
            "textContent_webdesign": _get_text("main_leistungen_webdesign"),
            "textContent_logos": _get_text("main_leistungen_logos"),
            "textContent_custom": _get_text("main_leistungen_custom"),
            "image_cms": _get_image("main_leistungen_cms_image"),
            "image_webdesign": _get_image("main_leistungen_webdesign_image"),
            "image_logo_1": _get_image("main_leistungen_logo_1") or legacy_logo_image,
            "image_logo_2": _get_image("main_leistungen_logo_2"),
            "image_logo_3": _get_image("main_leistungen_logo_3"),
            "image_logo_4": _get_image("main_leistungen_logo_4"),
            "image_custom": _get_image("main_leistungen_custom_image"),
            "textContent_visitenkarten": _get_text("main_leistungen_visitenkarten"),
            "image_vk_1": _get_image("main_leistungen_vk_1"),
            "image_vk_2": _get_image("main_leistungen_vk_2"),
            "image_vk_3": _get_image("main_leistungen_vk_3"),
            "image_vk_4": _get_image("main_leistungen_vk_4"),
            "textContent_medien": _get_text("main_leistungen_medien"),
            "image_medien": _get_image("main_leistungen_medien_image"),
        },
    )


@login_required(login_url="login")
def site_view_cmsinfo(request):
    return render(
        request,
        "pages/cms/content/sites/CmsInfoSite.html",
        {
            "textContent_hero": _get_text("main_cmsinfo_hero"),
            "textContent_sec1": _get_text("main_cmsinfo_sec1"),
            "textContent_sec2": _get_text("main_cmsinfo_sec2"),
            "textContent_feat1": _get_text("main_cmsinfo_feat1"),
            "textContent_feat2": _get_text("main_cmsinfo_feat2"),
            "textContent_feat3": _get_text("main_cmsinfo_feat3"),
            "textContent_feat4": _get_text("main_cmsinfo_feat4"),
            "textContent_feat5": _get_text("main_cmsinfo_feat5"),
            "textContent_feat6": _get_text("main_cmsinfo_feat6"),
            "textContent_feat7": _get_text("main_cmsinfo_feat7"),
            "textContent_feat8": _get_text("main_cmsinfo_feat8"),
            "textContent_feat9": _get_text("main_cmsinfo_feat9"),
            "textContent_demo": _get_text("main_cmsinfo_demo"),
            "textContent_products": _get_text("main_cmsinfo_products"),
            "textContent_products_bullet1": _get_text("main_cmsinfo_products_bullet1"),
            "textContent_products_bullet2": _get_text("main_cmsinfo_products_bullet2"),
            "textContent_products_bullet3": _get_text("main_cmsinfo_products_bullet3"),
            "textContent_products_bullet4": _get_text("main_cmsinfo_products_bullet4"),
            "textContent_security": _get_text("main_cmsinfo_security"),
            "textContent_security_bullet1": _get_text("main_cmsinfo_security_bullet1"),
            "textContent_security_bullet2": _get_text("main_cmsinfo_security_bullet2"),
            "textContent_security_bullet3": _get_text("main_cmsinfo_security_bullet3"),
            "textContent_security_bullet4": _get_text("main_cmsinfo_security_bullet4"),
            "textContent_blog": _get_text("main_cmsinfo_blog"),
            "textContent_blog_bullet1": _get_text("main_cmsinfo_blog_bullet1"),
            "textContent_blog_bullet2": _get_text("main_cmsinfo_blog_bullet2"),
            "textContent_blog_bullet3": _get_text("main_cmsinfo_blog_bullet3"),
            "textContent_company": _get_text("main_cmsinfo_company"),
            "textContent_company_bullet1": _get_text("main_cmsinfo_company_bullet1"),
            "textContent_company_bullet2": _get_text("main_cmsinfo_company_bullet2"),
            "textContent_company_bullet3": _get_text("main_cmsinfo_company_bullet3"),
            "textContent_company_bullet4": _get_text("main_cmsinfo_company_bullet4"),
            "textContent_trust": _get_text("main_cmsinfo_trust"),
            "textContent_stat1": _get_text("main_cmsinfo_stat1"),
            "textContent_stat2": _get_text("main_cmsinfo_stat2"),
            "textContent_stat3": _get_text("main_cmsinfo_stat3"),
            "textContent_stat4": _get_text("main_cmsinfo_stat4"),
            "textContent_bottomcta": _get_text("main_cmsinfo_bottomcta"),
            "image_shot_dashboard": _get_image("main_cmsinfo_shot_dashboard"),
            "image_sec1_preview_1": _get_image("main_cmsinfo_sec1_preview_1"),
            "image_sec1_preview_2": _get_image("main_cmsinfo_sec1_preview_2"),
            "image_sec1_preview_3": _get_image("main_cmsinfo_sec1_preview_3"),
            "image_sec1_preview_4": _get_image("main_cmsinfo_sec1_preview_4"),
            "image_sec2_preview_1": _get_image("main_cmsinfo_sec2_preview_1"),
            "image_sec2_preview_2": _get_image("main_cmsinfo_sec2_preview_2"),
            "image_sec2_preview_3": _get_image("main_cmsinfo_sec2_preview_3"),
            "image_blog": _get_image("main_cmsinfo_blog_image"),
            "image_company": _get_image("main_cmsinfo_company_image"),
            # Button-Slots: aktuell platzierter Button + Liste aller Buttons zur Auswahl
            "cmsinfo_btn_hero": Button.objects.filter(place="main_cmsinfo_hero_cta").order_by("order", "id").first(),
            "cmsinfo_btn_demo": Button.objects.filter(place="main_cmsinfo_demo_cta").order_by("order", "id").first(),
            "cmsinfo_btn_products": Button.objects.filter(place="main_cmsinfo_products_cta").order_by("order", "id").first(),
            "cmsinfo_btn_bottomcta": Button.objects.filter(place="main_cmsinfo_bottomcta").order_by("order", "id").first(),
            "all_buttons": Button.objects.order_by("order", "id"),
            "page_links": PageLink.objects.all(),
        },
    )


@login_required(login_url="login")
def site_view_logos(request):
    return render(
        request,
        "pages/cms/content/sites/LogosSite.html",
        {
            "textContent_hero": _get_text("main_logos_hero"),
            "textContent_hero_secondary": _get_text("main_logos_hero_secondary"),
            "image_hero_logo_1": _get_image("main_logos_hero_logo_1"),
            "image_hero_logo_2": _get_image("main_logos_hero_logo_2"),
            "image_hero_logo_3": _get_image("main_logos_hero_logo_3"),
            "image_hero_logo_4": _get_image("main_logos_hero_logo_4"),
            "image_hero_logo_5": _get_image("main_logos_hero_logo_5"),
            "textContent_warum": _get_text("main_logos_warum"),
            "textContent_warum_card1": _get_text("main_logos_warum_card1"),
            "textContent_warum_card2": _get_text("main_logos_warum_card2"),
            "textContent_warum_card3": _get_text("main_logos_warum_card3"),
            "textContent_leistungen": _get_text("main_logos_leistungen"),
            "textContent_leistungen_card1": _get_text("main_logos_leistungen_card1"),
            "textContent_leistungen_card1_bullet1": _get_text("main_logos_leistungen_card1_bullet1"),
            "textContent_leistungen_card1_bullet2": _get_text("main_logos_leistungen_card1_bullet2"),
            "textContent_leistungen_card1_bullet3": _get_text("main_logos_leistungen_card1_bullet3"),
            "textContent_leistungen_card2": _get_text("main_logos_leistungen_card2"),
            "textContent_leistungen_card2_bullet1": _get_text("main_logos_leistungen_card2_bullet1"),
            "textContent_leistungen_card2_bullet2": _get_text("main_logos_leistungen_card2_bullet2"),
            "textContent_leistungen_card2_bullet3": _get_text("main_logos_leistungen_card2_bullet3"),
            "textContent_leistungen_card3": _get_text("main_logos_leistungen_card3"),
            "textContent_leistungen_card3_bullet1": _get_text("main_logos_leistungen_card3_bullet1"),
            "textContent_leistungen_card3_bullet2": _get_text("main_logos_leistungen_card3_bullet2"),
            "textContent_leistungen_card3_bullet3": _get_text("main_logos_leistungen_card3_bullet3"),
            "textContent_leistungen_premium": _get_text("main_logos_leistungen_premium"),
            "textContent_leistungen_premium_bullet1": _get_text("main_logos_leistungen_premium_bullet1"),
            "textContent_leistungen_premium_bullet2": _get_text("main_logos_leistungen_premium_bullet2"),
            "textContent_leistungen_premium_bullet3": _get_text("main_logos_leistungen_premium_bullet3"),
            "textContent_leistungen_premium_bullet4": _get_text("main_logos_leistungen_premium_bullet4"),
            "textContent_premium": _get_text("main_logos_premium"),
            "textContent_premium_bullet1": _get_text("main_logos_premium_bullet1"),
            "textContent_premium_bullet2": _get_text("main_logos_premium_bullet2"),
            "textContent_premium_bullet3": _get_text("main_logos_premium_bullet3"),
            "textContent_prozess": _get_text("main_logos_prozess"),
            "textContent_prozess_step1": _get_text("main_logos_prozess_step1"),
            "textContent_prozess_step2": _get_text("main_logos_prozess_step2"),
            "textContent_prozess_step3": _get_text("main_logos_prozess_step3"),
            "textContent_prozess_step4": _get_text("main_logos_prozess_step4"),
            "textContent_prozess_step5": _get_text("main_logos_prozess_step5"),
            "textContent_lieferumfang": _get_text("main_logos_lieferumfang"),
            "textContent_lieferumfang_bullet1": _get_text("main_logos_lieferumfang_bullet1"),
            "textContent_lieferumfang_bullet2": _get_text("main_logos_lieferumfang_bullet2"),
            "textContent_lieferumfang_bullet3": _get_text("main_logos_lieferumfang_bullet3"),
            "textContent_lieferumfang_bullet4": _get_text("main_logos_lieferumfang_bullet4"),
            "textContent_lieferumfang_bullet5": _get_text("main_logos_lieferumfang_bullet5"),
            "textContent_usp": _get_text("main_logos_usp"),
            "textContent_usp_card1": _get_text("main_logos_usp_card1"),
            "textContent_usp_card2": _get_text("main_logos_usp_card2"),
            "textContent_usp_card3": _get_text("main_logos_usp_card3"),
            "textContent_bottomcta": _get_text("main_logos_bottomcta"),
        },
    )


@login_required(login_url="login")
def site_view_webdesign(request):
    return render(
        request,
        "pages/cms/content/sites/WebdesignSite.html",
        {
            "textContent_hero": _get_text("main_webdesign_hero"),
            "textContent_hero_secondary": _get_text("main_webdesign_hero_secondary"),
            "textContent_hero_badge1": _get_text("main_webdesign_hero_badge1"),
            "textContent_hero_badge2": _get_text("main_webdesign_hero_badge2"),
            "textContent_hero_badge3": _get_text("main_webdesign_hero_badge3"),
            "textContent_ansatz": _get_text("main_webdesign_ansatz"),
            "textContent_ansatz_card1": _get_text("main_webdesign_ansatz_card1"),
            "textContent_ansatz_card2": _get_text("main_webdesign_ansatz_card2"),
            "textContent_ansatz_card3": _get_text("main_webdesign_ansatz_card3"),
            "textContent_prozess": _get_text("main_webdesign_prozess"),
            "textContent_prozess_step1": _get_text("main_webdesign_prozess_step1"),
            "textContent_prozess_step2": _get_text("main_webdesign_prozess_step2"),
            "textContent_prozess_step3": _get_text("main_webdesign_prozess_step3"),
            "textContent_prozess_step4": _get_text("main_webdesign_prozess_step4"),
            "textContent_prozess_step5": _get_text("main_webdesign_prozess_step5"),
            "textContent_tech": _get_text("main_webdesign_tech"),
            "textContent_tech_bullet1": _get_text("main_webdesign_tech_bullet1"),
            "textContent_tech_bullet2": _get_text("main_webdesign_tech_bullet2"),
            "textContent_tech_bullet3": _get_text("main_webdesign_tech_bullet3"),
            "textContent_tech_bullet4": _get_text("main_webdesign_tech_bullet4"),
            "textContent_hosting": _get_text("main_webdesign_hosting"),
            "textContent_hosting_tile1": _get_text("main_webdesign_hosting_tile1"),
            "textContent_hosting_tile2": _get_text("main_webdesign_hosting_tile2"),
            "textContent_hosting_tile3": _get_text("main_webdesign_hosting_tile3"),
            "textContent_hosting_tile4": _get_text("main_webdesign_hosting_tile4"),
            "textContent_hosting_bullet1": _get_text("main_webdesign_hosting_bullet1"),
            "textContent_hosting_bullet2": _get_text("main_webdesign_hosting_bullet2"),
            "textContent_hosting_bullet3": _get_text("main_webdesign_hosting_bullet3"),
            "textContent_hosting_bullet4": _get_text("main_webdesign_hosting_bullet4"),
            "textContent_hosting_bullet5": _get_text("main_webdesign_hosting_bullet5"),
            "textContent_schwerpunkte": _get_text("main_webdesign_schwerpunkte"),
            "textContent_schwerpunkte_card1": _get_text("main_webdesign_schwerpunkte_card1"),
            "textContent_schwerpunkte_card1_bullet1": _get_text("main_webdesign_schwerpunkte_card1_bullet1"),
            "textContent_schwerpunkte_card1_bullet2": _get_text("main_webdesign_schwerpunkte_card1_bullet2"),
            "textContent_schwerpunkte_card1_bullet3": _get_text("main_webdesign_schwerpunkte_card1_bullet3"),
            "textContent_schwerpunkte_card2": _get_text("main_webdesign_schwerpunkte_card2"),
            "textContent_schwerpunkte_card2_bullet1": _get_text("main_webdesign_schwerpunkte_card2_bullet1"),
            "textContent_schwerpunkte_card2_bullet2": _get_text("main_webdesign_schwerpunkte_card2_bullet2"),
            "textContent_schwerpunkte_card2_bullet3": _get_text("main_webdesign_schwerpunkte_card2_bullet3"),
            "textContent_schwerpunkte_card3": _get_text("main_webdesign_schwerpunkte_card3"),
            "textContent_schwerpunkte_card3_bullet1": _get_text("main_webdesign_schwerpunkte_card3_bullet1"),
            "textContent_schwerpunkte_card3_bullet2": _get_text("main_webdesign_schwerpunkte_card3_bullet2"),
            "textContent_schwerpunkte_card3_bullet3": _get_text("main_webdesign_schwerpunkte_card3_bullet3"),
            "textContent_schwerpunkte_card4": _get_text("main_webdesign_schwerpunkte_card4"),
            "textContent_schwerpunkte_card4_bullet1": _get_text("main_webdesign_schwerpunkte_card4_bullet1"),
            "textContent_schwerpunkte_card4_bullet2": _get_text("main_webdesign_schwerpunkte_card4_bullet2"),
            "textContent_schwerpunkte_card4_bullet3": _get_text("main_webdesign_schwerpunkte_card4_bullet3"),
            "textContent_warum": _get_text("main_webdesign_warum"),
            "textContent_warum_card1": _get_text("main_webdesign_warum_card1"),
            "textContent_warum_card2": _get_text("main_webdesign_warum_card2"),
            "textContent_warum_card3": _get_text("main_webdesign_warum_card3"),
            "textContent_warum_card4": _get_text("main_webdesign_warum_card4"),
            "textContent_bottomcta": _get_text("main_webdesign_bottomcta"),
        },
    )


@login_required(login_url="login")
def site_view_webdesign_deggendorf(request):
    context = {
        # Hero
        "textContent_hero": _get_text("main_deggendorf_hero"),
        "textContent_hero_highlight": _get_text("main_deggendorf_hero_highlight"),
        "textContent_hero_secondary": _get_text("main_deggendorf_hero_secondary"),
        "image_skyline": _get_image("main_deggendorf_skyline"),
        # Intro
        "textContent_intro": _get_text("main_deggendorf_intro"),
        "textContent_intro_p2": _get_text("main_deggendorf_intro_p2"),
        "textContent_intro_caption": _get_text("main_deggendorf_intro_caption"),
        "image_intro": _get_image("main_deggendorf_intro_image"),
        # Warum YooLink
        "textContent_warum": _get_text("main_deggendorf_warum"),
        # Preise (Preiskarten zentral über die Preiskachel verwaltet)
        "textContent_preise": _get_text("main_deggendorf_preise"),
        "textContent_preise_footnote": _get_text("main_deggendorf_preise_footnote"),
        "pricing_count": PricingCard.objects.count(),
        # About / Über Deggendorf
        "textContent_about": _get_text("main_deggendorf_about"),
        "textContent_about_p2": _get_text("main_deggendorf_about_p2"),
        "textContent_about_caption": _get_text("main_deggendorf_about_caption"),
        "image_about": _get_image("main_deggendorf_about_image"),
        # Prozess
        "textContent_prozess": _get_text("main_deggendorf_prozess"),
        # Maps + Bottom CTA
        "textContent_maps": _get_text("main_deggendorf_maps"),
        "textContent_maps_panel": _get_text("main_deggendorf_maps_panel"),
        "textContent_maps_region": _get_text("main_deggendorf_maps_region"),
        "textContent_maps_response": _get_text("main_deggendorf_maps_response"),
        "textContent_bottomcta": _get_text("main_deggendorf_bottomcta"),
    }

    # Stat-Cards (4)
    for i in range(1, 5):
        context[f"textContent_hero_stat{i}"] = _get_text(f"main_deggendorf_hero_stat{i}")

    # Intro Bullets (4)
    for i in range(1, 5):
        context[f"textContent_intro_bullet{i}"] = _get_text(f"main_deggendorf_intro_bullet{i}")

    # Warum-Karten (6)
    for i in range(1, 7):
        context[f"textContent_warum_card{i}"] = _get_text(f"main_deggendorf_warum_card{i}")

    # About-Tiles (4)
    for i in range(1, 5):
        context[f"textContent_about_tile{i}"] = _get_text(f"main_deggendorf_about_tile{i}")

    # Prozess-Steps (4)
    for i in range(1, 5):
        context[f"textContent_prozess_step{i}"] = _get_text(f"main_deggendorf_prozess_step{i}")

    return render(request, "pages/cms/content/sites/WebdesignDeggendorfSite.html", context)


@login_required(login_url="login")
def site_view_visitenkarte(request):
    return render(
        request,
        "pages/cms/content/sites/VisitenkarteSite.html",
        {
            "textContent_hero": _get_text("main_visitenkarte_hero"),
            "textContent_hero_secondary": _get_text("main_visitenkarte_hero_secondary"),
            "image_hero_front": _get_image("main_visitenkarte_hero_front"),
            "image_hero_back": _get_image("main_visitenkarte_hero_back"),
            "textContent_showcase": _get_text("main_visitenkarte_showcase"),
            "textContent_showcase_label_front": _get_text("main_visitenkarte_showcase_label_front"),
            "textContent_showcase_label_back": _get_text("main_visitenkarte_showcase_label_back"),
            "image_showcase_front": _get_image("main_visitenkarte_showcase_front"),
            "image_showcase_back": _get_image("main_visitenkarte_showcase_back"),
            "textContent_formate": _get_text("main_visitenkarte_formate"),
            "textContent_format_standard": _get_text("main_visitenkarte_format_standard"),
            "textContent_format_slim": _get_text("main_visitenkarte_format_slim"),
            "textContent_papier": _get_text("main_visitenkarte_papier"),
            "textContent_papier_card1": _get_text("main_visitenkarte_papier_card1"),
            "textContent_papier_card2": _get_text("main_visitenkarte_papier_card2"),
            "textContent_papier_card3": _get_text("main_visitenkarte_papier_card3"),
            "textContent_bottomcta": _get_text("main_visitenkarte_bottomcta"),
        },
    )


@login_required(login_url="login")
def site_view_medien(request):
    context = {
        # Hero
        "textContent_hero": _get_text("main_medien_hero"),
        "textContent_hero_secondary": _get_text("main_medien_hero_secondary"),
        "textContent_hero_hint": _get_text("main_medien_hero_hint"),
        # Inhaltsarten
        "textContent_inhalte": _get_text("main_medien_inhalte"),
        # Prozess
        "textContent_prozess": _get_text("main_medien_prozess"),
        # Mehrwert / Aus einer Hand
        "textContent_mehrwert": _get_text("main_medien_mehrwert"),
        # Bottom CTA
        "textContent_bottomcta": _get_text("main_medien_bottomcta"),
    }

    # Inhaltsarten-Karten (4)
    for i in range(1, 5):
        context[f"textContent_inhalte_card{i}"] = _get_text(f"main_medien_inhalte_card{i}")

    # Prozess-Steps (3)
    for i in range(1, 4):
        context[f"textContent_prozess_step{i}"] = _get_text(f"main_medien_prozess_step{i}")

    # Mehrwert-Bullets (3)
    for i in range(1, 4):
        context[f"textContent_mehrwert_bullet{i}"] = _get_text(f"main_medien_mehrwert_bullet{i}")

    return render(request, "pages/cms/content/sites/MedienSite.html", context)


@login_required(login_url="login")
def site_view_datenschutz(request):
    lang = get_active_language(request)
    policy = PrivacyPolicy.objects.first()
    owner_data = WebsiteSettings.get_site_owner()
    privacy_content_html = ""
    if policy:
        privacy_content_html = getattr(policy, f"content_html_{lang}", "") or policy.content_html

    return render(
        request,
        "pages/cms/content/sites/DatenschutzSite.html",
        {
            "policy": policy,
            "privacy_content_html": privacy_content_html,
            "owner_data": owner_data,
            "cms_language": lang,
        },
    )


@login_required(login_url="login")
def site_view_cookies(request):
    return render(
        request,
        "pages/cms/content/sites/CookiesSite.html",
        {
            "textContent_hero": _get_text("main_cookies_hero"),
            "textContent_necessary": _get_text("main_cookies_necessary"),
            "textContent_analytics": _get_text("main_cookies_analytics"),
            "textContent_external": _get_text("main_cookies_external"),
            "textContent_actions": _get_text("main_cookies_actions"),
            "textContent_hinweis": _get_text("main_cookies_hinweis"),
        },
    )


@login_required(login_url="login")
def site_view_kontakt(request):
    return render(
        request,
        "pages/cms/content/sites/KontaktSite.html",
        {
            "textContent_hero": _get_text("main_kontakt_hero"),
            "textContent_panel": _get_text("main_kontakt_panel"),
            "textContent_panel_labels": _get_text("main_kontakt_panel_labels"),
            "textContent_opening_hours": _get_text("main_kontakt_opening_hours"),
            "textContent_response": _get_text("main_kontakt_response"),
            "textContent_form": _get_text("main_kontakt_form"),
            "textContent_fields": _get_text("main_kontakt_fields"),
            "textContent_message_placeholder": _get_text("main_kontakt_message_placeholder"),
            "textContent_success": _get_text("main_kontakt_success"),
        },
    )


@login_required(login_url="login")
def site_view_blog_overview(request):
    lang = get_active_language(request)
    return render(
        request,
        "pages/cms/content/sites/BlogOverviewSite.html",
        {
            "textContent_hero": _get_text("main_blog_overview_hero"),
            "cms_language": lang,
        },
    )


@login_required(login_url="login")
def save_text_content(request):
    if request.method != "POST":
        return JsonResponse({"error": "Etwas ist falsch gelaufen. Versuche es spÃ¤ter nochmal"}, status=400)

    lang = get_active_language(request)
    name = request.POST.get("name", "")

    custom_text = json.loads(request.POST.get("customText", "[]"))
    images = json.loads(request.POST.get("images", "[]"))
    galerien = json.loads(request.POST.get("galerien", "[]"))
    videos = json.loads(request.POST.get("videos", "[]"))
    buttons = json.loads(request.POST.get("buttons", "[]"))

    _assign_image_slots(images)
    _assign_gallery_slots(galerien)
    _assign_video_slots(videos)
    _assign_button_slots(buttons, lang)

    custom_keys = []
    for custom in custom_text:
        key = custom["key"]
        custom_keys.append(key)
        result = _save_text_values(key, custom["inputs"], lang)
        if result is not None:
            return result

    if name not in custom_keys:
        values = {
            "header": request.POST.get("header", ""),
            "title": request.POST.get("title", ""),
            "description": request.POST.get("description", ""),
            "buttonText": request.POST.get("buttonText", ""),
        }
        result = _save_text_values(name, values, lang)
        if result is not None:
            return result
        return JsonResponse({"success": "Element wurde erfolgreich gespeichert"}, status=200)

    return JsonResponse({"success": "Elemente wurden erfolgreich gespeichert"}, status=200)


def _assign_image_slots(images):
    for image in images:
        if fileentry.objects.filter(id=image["id"]).exists():
            file = fileentry.objects.get(id=image["id"])
            key = image["key"]
            if key:
                if fileentry.objects.filter(place=key).exists():
                    extra = fileentry.objects.get(place=key)
                    extra.place = "nothing"
                    extra.save()
                file.place = key
                file.save()


def _assign_gallery_slots(galerien):
    for galery in galerien:
        if Galerie.objects.filter(id=galery["id"]).exists():
            galerie = Galerie.objects.get(id=galery["id"])
            key = galery["key"]
            if key:
                if Galerie.objects.filter(place=key).exists():
                    extra = Galerie.objects.get(place=key)
                    extra.place = "nothing"
                    extra.save()
                galerie.place = key
                galerie.save()


def _assign_video_slots(videos):
    for video in videos:
        if VideoFile.objects.filter(id=video["id"]).exists():
            vid = VideoFile.objects.get(id=video["id"])
            key = video["key"]
            if key:
                if VideoFile.objects.filter(place=key).exists():
                    extra_vid = VideoFile.objects.get(place=key)
                    extra_vid.place = ""
                    extra_vid.save()
                vid.place = key
                vid.save()


def _assign_button_slots(buttons, lang):
    """Weist je Slot (place) genau EINEN Button zu und übernimmt dessen Felder
    (Text in aktiver Sprache, Design, Icon, Link, Tab). id == -1 leert den Slot."""
    valid_colors = {value for value, _ in Button.COLOR_CHOICES}
    for entry in buttons:
        key = (entry.get("key") or "").strip()
        if not key:
            continue

        bid = str(entry.get("id") or "-1")
        if bid in ("", "-1"):
            # Slot leeren: öffentliche Seite fällt auf den Standard-Link zurück
            Button.objects.filter(place=key).update(place="")
            continue

        btn = Button.objects.filter(id=bid).first()
        if not btn:
            continue

        # Slot exklusiv halten
        Button.objects.filter(place=key).exclude(id=btn.id).update(place="")
        btn.place = key

        text = (entry.get("text") or "").strip()
        if text:
            setattr(btn, f"text_{lang}", text)
            if lang == DEFAULT_LANGUAGE:
                btn.text = text

        color = entry.get("color")
        if color in valid_colors:
            btn.color = color

        btn.icon = (entry.get("icon") or "").strip()

        page_link_id = entry.get("page_link_id")
        btn.page_link = PageLink.objects.filter(id=page_link_id).first() if page_link_id else None
        btn.url = (entry.get("url") or "").strip()
        btn.target = "_blank" if entry.get("target") == "_blank" else "_self"

        btn.save()


def _save_text_values(name, values, lang):
    try:
        with transaction.atomic():
            text_content, created = TextContent.objects.get_or_create(name=name)

        for field in ["header", "title", "description", "buttonText"]:
            value = values.get(field, "")
            if created or value:
                setattr(text_content, f"{field}_{lang}", value)

        if lang == DEFAULT_LANGUAGE:
            for field in ["header", "title", "description", "buttonText"]:
                value = values.get(field, "")
                if created or value:
                    setattr(text_content, field, value)

        text_content.save()
    except IntegrityError:
        return JsonResponse({"error": f"Fehler: {name} existiert bereits"}, status=400)

    return None


@login_required(login_url="login")
def save_privacy_policy(request):
    if request.method != "POST":
        return JsonResponse({"error": "UngÃ¼ltige Anfrage"}, status=405)

    lang = get_active_language(request)
    content_html = request.POST.get("content_html", "")
    owner_data = WebsiteSettings.get_site_owner()
    policy, _ = PrivacyPolicy.objects.get_or_create(pk=1)
    prepared_content = PrivacyPolicy.prepare_content(content_html, owner_data, as_html=True)

    policy.use_html = True
    setattr(policy, f"content_html_{lang}", prepared_content)
    if lang == DEFAULT_LANGUAGE:
        policy.content_html = prepared_content
    policy.save(update_fields=["use_html", f"content_html_{lang}", "content_html", "updated_at"])

    return JsonResponse({"success": "DatenschutzerklÃ¤rung wurde gespeichert"}, status=200)


# ----------------------------------------------------------------------
# Impressum-Builder
# ----------------------------------------------------------------------


@login_required(login_url="login")
def site_view_impressum(request):
    lang = get_active_language(request)
    owner_data = WebsiteSettings.get_site_owner()
    blocks = ImpressumBlock.objects.all()

    return render(
        request,
        "pages/cms/content/sites/ImpressumSite.html",
        {
            "blocks": blocks,
            "owner_data": owner_data,
            "cms_language": lang,
        },
    )


@login_required(login_url="login")
@require_http_methods(["POST"])
def save_impressum(request):
    try:
        payload = json.loads(request.body or "{}")
    except (ValueError, TypeError):
        return JsonResponse({"error": "Ungültige Daten."}, status=400)

    blocks = payload.get("blocks", [])
    if not isinstance(blocks, list):
        return JsonResponse({"error": "Ungültige Daten."}, status=400)

    # In welcher Sprache wird gerade bearbeitet? (CMS-Sprachauswahl)
    lang = get_active_language(request)

    kept_ids = []
    with transaction.atomic():
        for index, raw in enumerate(blocks):
            title = (raw.get("title") or "").strip()
            content = (raw.get("content") or "").strip()
            active = bool(raw.get("active", True))

            block_id = raw.get("id")
            block = None
            if block_id not in (None, "", "null"):
                block = ImpressumBlock.objects.filter(id=block_id).first()

            # Bestehende Blöcke immer behalten (sie können Inhalte in der jeweils
            # anderen Sprache haben). Nur einen wirklich neuen, leeren Block
            # überspringen wir.
            if block is None:
                if not title and not content:
                    continue
                block = ImpressumBlock()

            # Nur die Felder der aktuell bearbeiteten Sprache schreiben.
            setattr(block, f"title_{lang}", title)
            setattr(block, f"content_{lang}", content)
            # Basisfeld an der modeltranslation-Default-Sprache (de) ausrichten,
            # damit der Fallback korrekt ist.
            if lang == "de":
                block.title = title
                block.content = content
            block.order = index
            block.active = active
            block.save()
            kept_ids.append(block.id)

        ImpressumBlock.objects.exclude(id__in=kept_ids).delete()

    return JsonResponse({"success": "Impressum wurde gespeichert"}, status=200)


# ----------------------------------------------------------------------
# Customer (Kunden) CMS-Views
# ----------------------------------------------------------------------

CUSTOMER_TRANSLATED_FIELDS = (
    "subtitle",
    "short_description",
    "description",
    "services_text",
    "testimonial",
    "testimonial_author",
)
CUSTOMER_PLAIN_FIELDS = (
    "name",
    "website_url",
    "website_display",
    "logo_fallback_text",
)


def _resolve_fileentry(value):
    if value in (None, "", 0, "0", "-1"):
        return None
    try:
        return fileentry.objects.get(pk=int(value))
    except (fileentry.DoesNotExist, TypeError, ValueError):
        return None


def _resolve_galerie(value):
    if value in (None, "", 0, "0", "-1"):
        return None
    try:
        return Galerie.objects.get(pk=int(value))
    except (Galerie.DoesNotExist, TypeError, ValueError):
        return None


def _apply_customer_payload(customer, payload, lang):
    is_create = customer.pk is None

    name = (payload.get("name") or "").strip()
    if not name:
        return "Name darf nicht leer sein"
    customer.name = name

    section = payload.get("section") or Customer.SECTION_REFERENCES
    if section not in dict(Customer.SECTION_CHOICES):
        section = Customer.SECTION_REFERENCES
    customer.section = section

    logo_style = payload.get("logo_style") or Customer.LOGO_STYLE_CIRCLE
    if logo_style not in dict(Customer.LOGO_STYLE_CHOICES):
        logo_style = Customer.LOGO_STYLE_CIRCLE
    customer.logo_style = logo_style

    customer.website_url = (payload.get("website_url") or "").strip()
    customer.website_display = (payload.get("website_display") or "").strip()
    customer.logo_fallback_text = (payload.get("logo_fallback_text") or "").strip()[:8]

    raw_date = (payload.get("published_date") or "").strip()
    if raw_date:
        try:
            from datetime import date

            year, month, day = (int(part) for part in raw_date.split("-"))
            customer.published_date = date(year, month, day)
        except (ValueError, TypeError):
            customer.published_date = None
    else:
        customer.published_date = None

    customer.active = bool(payload.get("active", True))
    customer.show_detail_page = bool(payload.get("show_detail_page", True))

    customer.title_image = _resolve_fileentry(payload.get("title_image_id"))
    customer.banner_image = _resolve_fileentry(payload.get("banner_image_id"))
    customer.logo = _resolve_fileentry(payload.get("logo_id"))
    customer.gallery = _resolve_galerie(payload.get("gallery_id"))

    for field in CUSTOMER_TRANSLATED_FIELDS:
        value = (payload.get(field) or "").strip()
        if is_create or value:
            setattr(customer, f"{field}_{lang}", value)
        if lang == DEFAULT_LANGUAGE and (is_create or value):
            setattr(customer, field, value)

    if is_create:
        max_order = Customer.objects.aggregate(m=Max("order"))["m"] or 0
        customer.order = max_order + 1

    customer.save()
    return None


@login_required(login_url="login")
def customer_list_view(request):
    customers = list(
        Customer.objects.select_related("title_image", "logo", "gallery")
        .order_by("section", "order", "id")
    )
    references = [c for c in customers if c.section == Customer.SECTION_REFERENCES]
    specials = [c for c in customers if c.section == Customer.SECTION_SPECIAL]

    total_count = len(customers)
    active_count = sum(1 for c in customers if c.active)
    inactive_count = total_count - active_count
    detail_count = sum(1 for c in customers if c.active and c.show_detail_page)

    return render(
        request,
        "pages/cms/content/customers/customer_list.html",
        {
            "references": references,
            "specials": specials,
            "total_count": total_count,
            "active_count": active_count,
            "inactive_count": inactive_count,
            "detail_count": detail_count,
        },
    )


@login_required(login_url="login")
def customer_create_view(request):
    if request.method == "GET":
        return render(
            request,
            "pages/cms/content/customers/customer_form.html",
            {
                "customer": None,
                "form_title": "Neuen Kunden erstellen",
                "submit_label": "Erstellen",
                "section_choices": Customer.SECTION_CHOICES,
                "logo_style_choices": Customer.LOGO_STYLE_CHOICES,
            },
        )

    if request.method != "POST":
        return JsonResponse({"error": "UngÃ¼ltige Anfrage"}, status=405)

    try:
        payload = json.loads(request.body)
    except (TypeError, ValueError):
        return JsonResponse({"error": "UngÃ¼ltige Daten"}, status=400)

    lang = get_active_language(request)
    customer = Customer()
    error = _apply_customer_payload(customer, payload, lang)
    if error:
        return JsonResponse({"error": error}, status=400)

    return JsonResponse(
        {"success": "Kunde wurde erstellt", "id": customer.id, "slug": customer.slug},
        status=201,
    )


@login_required(login_url="login")
def customer_edit_view(request, pk):
    customer = get_object_or_404(Customer, pk=pk)

    if request.method == "GET":
        return render(
            request,
            "pages/cms/content/customers/customer_form.html",
            {
                "customer": customer,
                "form_title": "Kunde bearbeiten",
                "submit_label": "Speichern",
                "section_choices": Customer.SECTION_CHOICES,
                "logo_style_choices": Customer.LOGO_STYLE_CHOICES,
            },
        )

    if request.method != "POST":
        return JsonResponse({"error": "UngÃ¼ltige Anfrage"}, status=405)

    try:
        payload = json.loads(request.body)
    except (TypeError, ValueError):
        return JsonResponse({"error": "UngÃ¼ltige Daten"}, status=400)

    lang = get_active_language(request)
    error = _apply_customer_payload(customer, payload, lang)
    if error:
        return JsonResponse({"error": error}, status=400)

    return JsonResponse(
        {"success": "Kunde wurde gespeichert", "id": customer.id, "slug": customer.slug},
        status=200,
    )


@login_required(login_url="login")
@require_http_methods(["POST", "DELETE"])
def customer_delete_view(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    customer.delete()
    return JsonResponse({"success": "Kunde wurde gelÃ¶scht"}, status=200)


# ----------------------------------------------------------------------
# ServiceLocation (Standorte / Einzugsgebiet) CMS-Views
# ----------------------------------------------------------------------


def _parse_coordinate(raw, minimum, maximum):
    """Koordinate aus User-Eingabe parsen – akzeptiert Komma und Punkt."""
    if raw in (None, ""):
        return None
    try:
        value = Decimal(str(raw).strip().replace(",", "."))
    except (InvalidOperation, ValueError):
        return None
    if value < minimum or value > maximum:
        return None
    return value.quantize(Decimal("0.000001"))


def _apply_location_payload(location, payload):
    name = (payload.get("name") or "").strip()
    if not name:
        return "Name darf nicht leer sein"

    latitude = _parse_coordinate(payload.get("latitude"), Decimal("-90"), Decimal("90"))
    longitude = _parse_coordinate(payload.get("longitude"), Decimal("-180"), Decimal("180"))
    if latitude is None or longitude is None:
        return "Bitte gültige Koordinaten angeben (z. B. 48.8372 und 12.9516)"

    location.name = name[:120]
    location.tagline = (payload.get("tagline") or "").strip()[:160]
    location.url = (payload.get("url") or "").strip()[:300]
    location.latitude = latitude
    location.longitude = longitude
    location.is_headquarters = bool(payload.get("is_headquarters", False))
    location.active = bool(payload.get("active", True))

    if location.pk is None:
        max_order = ServiceLocation.objects.aggregate(m=Max("order"))["m"] or 0
        location.order = max_order + 1

    location.save()

    # Es kann nur einen Hauptsitz geben
    if location.is_headquarters:
        ServiceLocation.objects.exclude(pk=location.pk).update(is_headquarters=False)

    return None


@login_required(login_url="login")
def location_list_view(request):
    locations = list(ServiceLocation.objects.all())
    active_locations = [loc for loc in locations if loc.active]

    return render(
        request,
        "pages/cms/content/locations/location_list.html",
        {
            "locations": locations,
            "active_locations": active_locations,
            "total_count": len(locations),
            "active_count": len(active_locations),
            "linked_count": sum(1 for loc in locations if loc.has_landing_page),
            "area_count": sum(1 for loc in locations if not loc.has_landing_page),
            "map_lng_min": ServiceLocation.MAP_LNG_MIN,
            "map_lng_max": ServiceLocation.MAP_LNG_MAX,
            "map_lat_min": ServiceLocation.MAP_LAT_MIN,
            "map_lat_max": ServiceLocation.MAP_LAT_MAX,
        },
    )


@login_required(login_url="login")
def location_create_view(request):
    if request.method != "POST":
        return JsonResponse({"error": "Ungültige Anfrage"}, status=405)

    try:
        payload = json.loads(request.body)
    except (TypeError, ValueError):
        return JsonResponse({"error": "Ungültige Daten"}, status=400)

    location = ServiceLocation()
    error = _apply_location_payload(location, payload)
    if error:
        return JsonResponse({"error": error}, status=400)

    return JsonResponse({"success": "Standort wurde erstellt", "id": location.id}, status=201)


@login_required(login_url="login")
def location_edit_view(request, pk):
    location = get_object_or_404(ServiceLocation, pk=pk)

    if request.method != "POST":
        return JsonResponse({"error": "Ungültige Anfrage"}, status=405)

    try:
        payload = json.loads(request.body)
    except (TypeError, ValueError):
        return JsonResponse({"error": "Ungültige Daten"}, status=400)

    error = _apply_location_payload(location, payload)
    if error:
        return JsonResponse({"error": error}, status=400)

    return JsonResponse({"success": "Standort wurde gespeichert", "id": location.id}, status=200)


@login_required(login_url="login")
@require_http_methods(["POST", "DELETE"])
def location_delete_view(request, pk):
    location = get_object_or_404(ServiceLocation, pk=pk)
    location.delete()
    return JsonResponse({"success": "Standort wurde gelöscht"}, status=200)


@login_required(login_url="login")
def location_reorder_view(request):
    if request.method != "POST":
        return JsonResponse({"error": "Ungültige Anfrage"}, status=405)

    try:
        payload = json.loads(request.body)
    except (TypeError, ValueError):
        return JsonResponse({"error": "Ungültige Daten"}, status=400)

    order = payload.get("order") or []
    if not isinstance(order, list):
        return JsonResponse({"error": "Ungültige Reihenfolge"}, status=400)

    try:
        ids = [int(x) for x in order]
    except (TypeError, ValueError):
        return JsonResponse({"error": "Ungültige IDs"}, status=400)

    for index, location_id in enumerate(ids, start=1):
        ServiceLocation.objects.filter(pk=location_id).update(order=index)

    return JsonResponse({"success": "Reihenfolge gespeichert"}, status=200)


@login_required(login_url="login")
def customer_reorder_view(request):
    if request.method != "POST":
        return JsonResponse({"error": "UngÃ¼ltige Anfrage"}, status=405)

    try:
        payload = json.loads(request.body)
    except (TypeError, ValueError):
        return JsonResponse({"error": "UngÃ¼ltige Daten"}, status=400)

    order = payload.get("order") or []
    if not isinstance(order, list):
        return JsonResponse({"error": "UngÃ¼ltige Reihenfolge"}, status=400)

    try:
        ids = [int(x) for x in order]
    except (TypeError, ValueError):
        return JsonResponse({"error": "UngÃ¼ltige IDs"}, status=400)

    for index, customer_id in enumerate(ids, start=1):
        Customer.objects.filter(pk=customer_id).update(order=index)

    return JsonResponse({"success": "Reihenfolge gespeichert"}, status=200)
