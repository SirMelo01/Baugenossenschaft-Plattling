from django.shortcuts import render, redirect, get_object_or_404
from yoolink.ycms.applications.content.models import Customer, ImpressumBlock, PrivacyPolicy, ServiceLocation, TextContent
from yoolink.ycms.models import FAQ, Message, PricingCard, TeamMember, fileentry, Galerie, OpeningHours, WebsiteSettings, Button
import datetime
from django.http import Http404, HttpResponseRedirect
from django.utils.translation import get_language_from_request, activate
from django.conf import settings

def get_opening_hours():
    opening_hours = {}
    website_settings = WebsiteSettings.get_solo()
    days = [
        ("MON", "opening_day_monday"),
        ("TUE", "opening_day_tuesday"),
        ("WED", "opening_day_wednesday"),
        ("THU", "opening_day_thursday"),
        ("FRI", "opening_day_friday"),
        ("SAT", "opening_day_saturday"),
        ("SUN", "opening_day_sunday"),
    ]
    opening_hours_rows = []
    for day, day_label in days:
        opening_hour = OpeningHours.objects.filter(
            website=website_settings,
            day=day,
        ).first()
        opening_hours[f"opening_{day.lower()}"] = opening_hour

        periods = []
        if opening_hour:
            periods = [
                f"{start.strftime('%H:%M')} - {end.strftime('%H:%M')}"
                for start, end in opening_hour.calculate_opening_periods()
            ]

        opening_hours_rows.append(
            {
                "day": day,
                "label_key": day_label,
                "is_open": bool(opening_hour and opening_hour.is_open),
                "periods": periods,
            }
        )

    opening_hours["opening_hours_rows"] = opening_hours_rows
    opening_hours["has_opening_hours"] = any(row["is_open"] for row in opening_hours_rows)
        
    # Muss überall sein
    if TextContent.objects.filter(name="footer").exists():
        opening_hours["footerText"] = TextContent.objects.get(name='footer')
        
    return opening_hours

def load_kunden(request):
    context = {}
    context.update(get_opening_hours())

    if TextContent.objects.filter(name="main_kunden").exists():
        context["kundenText"] = TextContent.objects.get(name='main_kunden')

    if TextContent.objects.filter(name="main_kunden2").exists():
        context["kundenText2"] = TextContent.objects.get(name='main_kunden2')

    if TextContent.objects.filter(name="main_kunden_references").exists():
        context["kundenReferences"] = TextContent.objects.get(name='main_kunden_references')

    context["textContent_bottomcta"] = TextContent.objects.filter(name="main_kunden_bottomcta").first()

    customers_qs = list(
        Customer.objects.filter(active=True)
        .select_related("title_image", "logo")
        .order_by("order", "-published_date", "id")
    )
    references = [c for c in customers_qs if c.section == Customer.SECTION_REFERENCES]
    specials = [c for c in customers_qs if c.section == Customer.SECTION_SPECIAL]
    context["customers_references"] = references
    context["customers_special"] = specials
    context["customers_total"] = len(references) + len(specials)

    return render(request, 'pages/kunden.html', context=context)


def load_kunde_detail(request, slug):
    customer = (
        Customer.objects.filter(slug=slug, active=True, show_detail_page=True)
        .select_related("title_image", "banner_image", "logo", "gallery")
        .first()
    )
    if not customer:
        raise Http404("Kunde nicht gefunden")

    gallery_images = []
    if customer.gallery:
        gallery_images = list(customer.gallery.images.all())

    services = [line.strip() for line in (customer.services_text or "").splitlines() if line.strip()]

    related_customers = (
        Customer.objects.filter(active=True, show_detail_page=True)
        .exclude(pk=customer.pk)
        .order_by("-published_date", "order")[:3]
    )

    context = {
        "customer": customer,
        "gallery_images": gallery_images,
        "services": services,
        "related_customers": related_customers,
    }
    context.update(get_opening_hours())
    return render(request, "pages/kunde_detail.html", context=context)

def load_index(request):
    faq = FAQ.objects.all()

    context = {
        'FAQ': faq,
    }

    # Text Contents
    if TextContent.objects.filter(name="main_hero").exists():
        context["heroText"] = TextContent.objects.get(name='main_hero')

    if TextContent.objects.filter(name="main_responsive").exists():
        context["responsiveText"] = TextContent.objects.get(name='main_responsive')

    if TextContent.objects.filter(name="main_cms").exists():
        context["cmsText"] = TextContent.objects.get(name='main_cms')

    if TextContent.objects.filter(name="main_price").exists():
        context["priceText"] = TextContent.objects.get(name='main_price')

    if TextContent.objects.filter(name="main_team").exists():
        context["teamText"] = TextContent.objects.get(name='main_team')

    if TextContent.objects.filter(name="main_kunden").exists():
        context["kundenText"] = TextContent.objects.get(name='main_kunden')
    # Text Know-How
    if TextContent.objects.filter(name="main_know_how").exists():
        context["knowHowContent"] = TextContent.objects.get(name='main_know_how')
    # Know How contents
    if TextContent.objects.filter(name="main_know_how_card_1").exists():
        context["knowHowContentCard1"] = TextContent.objects.get(name='main_know_how_card_1')
    if TextContent.objects.filter(name="main_know_how_card_2").exists():
        context["knowHowContentCard2"] = TextContent.objects.get(name='main_know_how_card_2')
    if TextContent.objects.filter(name="main_know_how_card_3").exists():
        context["knowHowContentCard3"] = TextContent.objects.get(name='main_know_how_card_3')
    if TextContent.objects.filter(name="main_faq").exists():
        context["faqText"] = TextContent.objects.get(name='main_faq')
    # Galery
    if Galerie.objects.filter(place='main_hero').exists():
        context["heroImages"] = Galerie.objects.get(place='main_hero').images.all()
        
    if Galerie.objects.filter(place='main_responsive_desktop').exists():
        context['responsiveDesktopImages'] = Galerie.objects.get(place='main_responsive_desktop').images.all()
        
    if Galerie.objects.filter(place='main_responsive_handy').exists():
        context['responsiveHandyImages'] = Galerie.objects.get(place='main_responsive_handy').images.all()

    pricing_cards = PricingCard.objects.select_related("button").prefetch_related("features").filter(active=True)
    context["pricing_cards"] = pricing_cards

    # Images
    if fileentry.objects.filter(place='main_cms').exists():
        context["cmsImage"] = fileentry.objects.get(place='main_cms')
    
    # Mitarbeiter
    active_team_members = TeamMember.objects.filter(active=True)
    context['teamMembers'] = active_team_members

    # Referenzen (dynamisch aus dem CMS) - nur die ersten drei für die Startseite
    context["customers_references"] = list(
        Customer.objects.filter(active=True, section=Customer.SECTION_REFERENCES)
        .select_related("title_image", "logo")
        .order_by("order", "-published_date", "id")[:3]
    )

    # Standorte / Einzugsgebiet (Karte mit lokalen Landingpages)
    if TextContent.objects.filter(name="main_standorte").exists():
        context["standorteText"] = TextContent.objects.get(name="main_standorte")
    service_locations = list(ServiceLocation.objects.filter(active=True))
    context["service_locations"] = service_locations
    context["standorte_linked"] = [loc for loc in service_locations if loc.has_landing_page]

    context.update(get_opening_hours())

    return render(request, 'pages/index.html', context=context)


def load_logos(request):
    context = {}
    context.update(get_opening_hours())

    def get_text(name: str):
        return TextContent.objects.filter(name=name).first()

    def get_image(place: str):
        return fileentry.objects.filter(place=place).first()

    # Hero
    context["textContent_hero"] = get_text("main_logos_hero")
    context["textContent_hero_secondary"] = get_text("main_logos_hero_secondary")
    context["image_hero_logo_1"] = get_image("main_logos_hero_logo_1")
    context["image_hero_logo_2"] = get_image("main_logos_hero_logo_2")
    context["image_hero_logo_3"] = get_image("main_logos_hero_logo_3")
    context["image_hero_logo_4"] = get_image("main_logos_hero_logo_4")
    context["image_hero_logo_5"] = get_image("main_logos_hero_logo_5")

    # Warum
    context["textContent_warum"] = get_text("main_logos_warum")
    context["textContent_warum_card1"] = get_text("main_logos_warum_card1")
    context["textContent_warum_card2"] = get_text("main_logos_warum_card2")
    context["textContent_warum_card3"] = get_text("main_logos_warum_card3")

    # Leistungsbereiche
    context["textContent_leistungen"] = get_text("main_logos_leistungen")
    context["textContent_leistungen_card1"] = get_text("main_logos_leistungen_card1")
    context["textContent_leistungen_card1_bullet1"] = get_text("main_logos_leistungen_card1_bullet1")
    context["textContent_leistungen_card1_bullet2"] = get_text("main_logos_leistungen_card1_bullet2")
    context["textContent_leistungen_card1_bullet3"] = get_text("main_logos_leistungen_card1_bullet3")
    context["textContent_leistungen_card2"] = get_text("main_logos_leistungen_card2")
    context["textContent_leistungen_card2_bullet1"] = get_text("main_logos_leistungen_card2_bullet1")
    context["textContent_leistungen_card2_bullet2"] = get_text("main_logos_leistungen_card2_bullet2")
    context["textContent_leistungen_card2_bullet3"] = get_text("main_logos_leistungen_card2_bullet3")
    context["textContent_leistungen_card3"] = get_text("main_logos_leistungen_card3")
    context["textContent_leistungen_card3_bullet1"] = get_text("main_logos_leistungen_card3_bullet1")
    context["textContent_leistungen_card3_bullet2"] = get_text("main_logos_leistungen_card3_bullet2")
    context["textContent_leistungen_card3_bullet3"] = get_text("main_logos_leistungen_card3_bullet3")
    context["textContent_leistungen_premium"] = get_text("main_logos_leistungen_premium")
    context["textContent_leistungen_premium_bullet1"] = get_text("main_logos_leistungen_premium_bullet1")
    context["textContent_leistungen_premium_bullet2"] = get_text("main_logos_leistungen_premium_bullet2")
    context["textContent_leistungen_premium_bullet3"] = get_text("main_logos_leistungen_premium_bullet3")
    context["textContent_leistungen_premium_bullet4"] = get_text("main_logos_leistungen_premium_bullet4")

    # Premium Showcase (Goldener Schnitt)
    context["textContent_premium"] = get_text("main_logos_premium")
    context["textContent_premium_bullet1"] = get_text("main_logos_premium_bullet1")
    context["textContent_premium_bullet2"] = get_text("main_logos_premium_bullet2")
    context["textContent_premium_bullet3"] = get_text("main_logos_premium_bullet3")

    # Designprozess
    context["textContent_prozess"] = get_text("main_logos_prozess")
    context["textContent_prozess_step1"] = get_text("main_logos_prozess_step1")
    context["textContent_prozess_step2"] = get_text("main_logos_prozess_step2")
    context["textContent_prozess_step3"] = get_text("main_logos_prozess_step3")
    context["textContent_prozess_step4"] = get_text("main_logos_prozess_step4")
    context["textContent_prozess_step5"] = get_text("main_logos_prozess_step5")

    # Lieferumfang
    context["textContent_lieferumfang"] = get_text("main_logos_lieferumfang")
    context["textContent_lieferumfang_bullet1"] = get_text("main_logos_lieferumfang_bullet1")
    context["textContent_lieferumfang_bullet2"] = get_text("main_logos_lieferumfang_bullet2")
    context["textContent_lieferumfang_bullet3"] = get_text("main_logos_lieferumfang_bullet3")
    context["textContent_lieferumfang_bullet4"] = get_text("main_logos_lieferumfang_bullet4")
    context["textContent_lieferumfang_bullet5"] = get_text("main_logos_lieferumfang_bullet5")

    # USP
    context["textContent_usp"] = get_text("main_logos_usp")
    context["textContent_usp_card1"] = get_text("main_logos_usp_card1")
    context["textContent_usp_card2"] = get_text("main_logos_usp_card2")
    context["textContent_usp_card3"] = get_text("main_logos_usp_card3")

    # Bottom CTA
    context["textContent_bottomcta"] = get_text("main_logos_bottomcta")

    return render(request, 'pages/leistungen_logos.html', context=context)


def load_medien(request):
    context = {}
    context.update(get_opening_hours())

    def get_text(name: str):
        return TextContent.objects.filter(name=name).first()

    # Hero
    context["textContent_hero"] = get_text("main_medien_hero")
    context["textContent_hero_secondary"] = get_text("main_medien_hero_secondary")
    context["textContent_hero_hint"] = get_text("main_medien_hero_hint")

    # Inhaltsarten (Section + 4 Cards)
    context["textContent_inhalte"] = get_text("main_medien_inhalte")
    for i in range(1, 5):
        context[f"textContent_inhalte_card{i}"] = get_text(f"main_medien_inhalte_card{i}")

    # Prozess (Section + 3 Steps)
    context["textContent_prozess"] = get_text("main_medien_prozess")
    for i in range(1, 4):
        context[f"textContent_prozess_step{i}"] = get_text(f"main_medien_prozess_step{i}")

    # Mehrwert / Aus einer Hand (Section + 3 Bullets)
    context["textContent_mehrwert"] = get_text("main_medien_mehrwert")
    for i in range(1, 4):
        context[f"textContent_mehrwert_bullet{i}"] = get_text(f"main_medien_mehrwert_bullet{i}")

    # Bottom CTA
    context["textContent_bottomcta"] = get_text("main_medien_bottomcta")

    return render(request, 'pages/leistungen_medien.html', context=context)


def load_webdesign_deggendorf(request):
    context = {
        'google_maps_embed_api_key': settings.GOOGLE_MAPS_EMBED_API_KEY,
    }
    context.update(get_opening_hours())

    def get_text(name: str):
        return TextContent.objects.filter(name=name).first()

    def get_image(place: str):
        return fileentry.objects.filter(place=place).first()

    # Hero (mit Skyline-Hintergrund / Stadtübersicht)
    context["textContent_hero"] = get_text("main_deggendorf_hero")
    context["textContent_hero_highlight"] = get_text("main_deggendorf_hero_highlight")
    context["textContent_hero_secondary"] = get_text("main_deggendorf_hero_secondary")
    context["image_skyline"] = get_image("main_deggendorf_skyline")
    for i in range(1, 5):
        context[f"textContent_hero_stat{i}"] = get_text(f"main_deggendorf_hero_stat{i}")

    # Intro (mit Grabkirche)
    context["textContent_intro"] = get_text("main_deggendorf_intro")
    context["textContent_intro_p2"] = get_text("main_deggendorf_intro_p2")
    context["textContent_intro_caption"] = get_text("main_deggendorf_intro_caption")
    context["image_intro"] = get_image("main_deggendorf_intro_image")
    for i in range(1, 5):
        context[f"textContent_intro_bullet{i}"] = get_text(f"main_deggendorf_intro_bullet{i}")

    # Warum YooLink (USP Cards)
    context["textContent_warum"] = get_text("main_deggendorf_warum")
    for i in range(1, 7):
        context[f"textContent_warum_card{i}"] = get_text(f"main_deggendorf_warum_card{i}")

    # Preise / Abo-Modelle (geteilte Preiskacheln, identisch zur Hauptseite)
    context["textContent_preise"] = get_text("main_deggendorf_preise")
    context["textContent_preise_footnote"] = get_text("main_deggendorf_preise_footnote")
    context["pricing_cards"] = (
        PricingCard.objects.select_related("button")
        .prefetch_related("features")
        .filter(active=True)
    )

    # About / Über Deggendorf (mit Altem Rathaus)
    context["textContent_about"] = get_text("main_deggendorf_about")
    context["textContent_about_p2"] = get_text("main_deggendorf_about_p2")
    context["textContent_about_caption"] = get_text("main_deggendorf_about_caption")
    context["image_about"] = get_image("main_deggendorf_about_image")
    for i in range(1, 5):
        context[f"textContent_about_tile{i}"] = get_text(f"main_deggendorf_about_tile{i}")

    # Prozess / Vorgehen
    context["textContent_prozess"] = get_text("main_deggendorf_prozess")
    for i in range(1, 5):
        context[f"textContent_prozess_step{i}"] = get_text(f"main_deggendorf_prozess_step{i}")

    # Maps + Bottom CTA
    context["textContent_maps"] = get_text("main_deggendorf_maps")
    context["textContent_maps_panel"] = get_text("main_deggendorf_maps_panel")
    context["textContent_maps_region"] = get_text("main_deggendorf_maps_region")
    context["textContent_maps_response"] = get_text("main_deggendorf_maps_response")
    context["textContent_bottomcta"] = get_text("main_deggendorf_bottomcta")

    return render(request, 'pages/webdesign_deggendorf.html', context=context)


def load_webdesign(request):
    context = {}
    context.update(get_opening_hours())

    def get_text(name: str):
        return TextContent.objects.filter(name=name).first()

    # Hero
    context["textContent_hero"] = get_text("main_webdesign_hero")
    context["textContent_hero_secondary"] = get_text("main_webdesign_hero_secondary")
    context["textContent_hero_badge1"] = get_text("main_webdesign_hero_badge1")
    context["textContent_hero_badge2"] = get_text("main_webdesign_hero_badge2")
    context["textContent_hero_badge3"] = get_text("main_webdesign_hero_badge3")

    # Ansatz
    context["textContent_ansatz"] = get_text("main_webdesign_ansatz")
    context["textContent_ansatz_card1"] = get_text("main_webdesign_ansatz_card1")
    context["textContent_ansatz_card2"] = get_text("main_webdesign_ansatz_card2")
    context["textContent_ansatz_card3"] = get_text("main_webdesign_ansatz_card3")

    # Prozess
    context["textContent_prozess"] = get_text("main_webdesign_prozess")
    context["textContent_prozess_step1"] = get_text("main_webdesign_prozess_step1")
    context["textContent_prozess_step2"] = get_text("main_webdesign_prozess_step2")
    context["textContent_prozess_step3"] = get_text("main_webdesign_prozess_step3")
    context["textContent_prozess_step4"] = get_text("main_webdesign_prozess_step4")
    context["textContent_prozess_step5"] = get_text("main_webdesign_prozess_step5")

    # Tech Stack
    context["textContent_tech"] = get_text("main_webdesign_tech")
    context["textContent_tech_bullet1"] = get_text("main_webdesign_tech_bullet1")
    context["textContent_tech_bullet2"] = get_text("main_webdesign_tech_bullet2")
    context["textContent_tech_bullet3"] = get_text("main_webdesign_tech_bullet3")
    context["textContent_tech_bullet4"] = get_text("main_webdesign_tech_bullet4")

    # Hosting bei Hetzner
    context["textContent_hosting"] = get_text("main_webdesign_hosting")
    context["textContent_hosting_tile1"] = get_text("main_webdesign_hosting_tile1")
    context["textContent_hosting_tile2"] = get_text("main_webdesign_hosting_tile2")
    context["textContent_hosting_tile3"] = get_text("main_webdesign_hosting_tile3")
    context["textContent_hosting_tile4"] = get_text("main_webdesign_hosting_tile4")
    context["textContent_hosting_bullet1"] = get_text("main_webdesign_hosting_bullet1")
    context["textContent_hosting_bullet2"] = get_text("main_webdesign_hosting_bullet2")
    context["textContent_hosting_bullet3"] = get_text("main_webdesign_hosting_bullet3")
    context["textContent_hosting_bullet4"] = get_text("main_webdesign_hosting_bullet4")
    context["textContent_hosting_bullet5"] = get_text("main_webdesign_hosting_bullet5")

    # Technische Schwerpunkte
    context["textContent_schwerpunkte"] = get_text("main_webdesign_schwerpunkte")
    context["textContent_schwerpunkte_card1"] = get_text("main_webdesign_schwerpunkte_card1")
    context["textContent_schwerpunkte_card1_bullet1"] = get_text("main_webdesign_schwerpunkte_card1_bullet1")
    context["textContent_schwerpunkte_card1_bullet2"] = get_text("main_webdesign_schwerpunkte_card1_bullet2")
    context["textContent_schwerpunkte_card1_bullet3"] = get_text("main_webdesign_schwerpunkte_card1_bullet3")
    context["textContent_schwerpunkte_card2"] = get_text("main_webdesign_schwerpunkte_card2")
    context["textContent_schwerpunkte_card2_bullet1"] = get_text("main_webdesign_schwerpunkte_card2_bullet1")
    context["textContent_schwerpunkte_card2_bullet2"] = get_text("main_webdesign_schwerpunkte_card2_bullet2")
    context["textContent_schwerpunkte_card2_bullet3"] = get_text("main_webdesign_schwerpunkte_card2_bullet3")
    context["textContent_schwerpunkte_card3"] = get_text("main_webdesign_schwerpunkte_card3")
    context["textContent_schwerpunkte_card3_bullet1"] = get_text("main_webdesign_schwerpunkte_card3_bullet1")
    context["textContent_schwerpunkte_card3_bullet2"] = get_text("main_webdesign_schwerpunkte_card3_bullet2")
    context["textContent_schwerpunkte_card3_bullet3"] = get_text("main_webdesign_schwerpunkte_card3_bullet3")
    context["textContent_schwerpunkte_card4"] = get_text("main_webdesign_schwerpunkte_card4")
    context["textContent_schwerpunkte_card4_bullet1"] = get_text("main_webdesign_schwerpunkte_card4_bullet1")
    context["textContent_schwerpunkte_card4_bullet2"] = get_text("main_webdesign_schwerpunkte_card4_bullet2")
    context["textContent_schwerpunkte_card4_bullet3"] = get_text("main_webdesign_schwerpunkte_card4_bullet3")

    # Warum dieser Ansatz
    context["textContent_warum"] = get_text("main_webdesign_warum")
    context["textContent_warum_card1"] = get_text("main_webdesign_warum_card1")
    context["textContent_warum_card2"] = get_text("main_webdesign_warum_card2")
    context["textContent_warum_card3"] = get_text("main_webdesign_warum_card3")
    context["textContent_warum_card4"] = get_text("main_webdesign_warum_card4")

    # Bottom CTA
    context["textContent_bottomcta"] = get_text("main_webdesign_bottomcta")

    return render(request, 'pages/leistungen_webdesign.html', context=context)


def load_visitenkarte(request):
    context = {}
    context.update(get_opening_hours())

    def get_text(name: str):
        return TextContent.objects.filter(name=name).first()

    def get_image(place: str):
        return fileentry.objects.filter(place=place).first()

    # Hero
    context["textContent_hero"] = get_text("main_visitenkarte_hero")
    context["textContent_hero_secondary"] = get_text("main_visitenkarte_hero_secondary")
    context["image_hero_front"] = get_image("main_visitenkarte_hero_front")
    context["image_hero_back"] = get_image("main_visitenkarte_hero_back")

    # Showcase / Bisherige Arbeiten
    context["textContent_showcase"] = get_text("main_visitenkarte_showcase")
    context["textContent_showcase_label_front"] = get_text("main_visitenkarte_showcase_label_front")
    context["textContent_showcase_label_back"] = get_text("main_visitenkarte_showcase_label_back")
    context["image_showcase_front"] = get_image("main_visitenkarte_showcase_front")
    context["image_showcase_back"] = get_image("main_visitenkarte_showcase_back")

    # Formate
    context["textContent_formate"] = get_text("main_visitenkarte_formate")
    context["textContent_format_standard"] = get_text("main_visitenkarte_format_standard")
    context["textContent_format_slim"] = get_text("main_visitenkarte_format_slim")

    # Papier / Qualität
    context["textContent_papier"] = get_text("main_visitenkarte_papier")
    context["textContent_papier_card1"] = get_text("main_visitenkarte_papier_card1")
    context["textContent_papier_card2"] = get_text("main_visitenkarte_papier_card2")
    context["textContent_papier_card3"] = get_text("main_visitenkarte_papier_card3")

    # Bottom CTA
    context["textContent_bottomcta"] = get_text("main_visitenkarte_bottomcta")

    return render(request, 'pages/leistungen_visitenkarte.html', context=context)


def load_cmsinfo(request):
    context = {}

    def get_text(name: str):
        return TextContent.objects.filter(name=name).first()

    def get_image(place: str):
        return fileentry.objects.filter(place=place).first()

    context["textContent_hero"] = TextContent.objects.filter(name="main_cmsinfo_hero").first()
    context["textContent_sec1"] = get_text("main_cmsinfo_sec1")
    context["textContent_sec2"] = get_text("main_cmsinfo_sec2")

    # Feature-Grid-Kacheln (Titel + Beschreibung editierbar, Icons bleiben fest)
    for i in range(1, 10):
        context[f"textContent_feat{i}"] = get_text(f"main_cmsinfo_feat{i}")

    # Demo-, Produkte- und Sicherheitssektion + deren Bullets
    context["textContent_demo"] = get_text("main_cmsinfo_demo")
    context["textContent_products"] = get_text("main_cmsinfo_products")
    context["textContent_security"] = get_text("main_cmsinfo_security")
    for i in range(1, 5):
        context[f"textContent_products_bullet{i}"] = get_text(f"main_cmsinfo_products_bullet{i}")
        context[f"textContent_security_bullet{i}"] = get_text(f"main_cmsinfo_security_bullet{i}")

    context["textContent_blog"] = get_text("main_cmsinfo_blog")
    context["textContent_blog_bullet1"] = get_text("main_cmsinfo_blog_bullet1")
    context["textContent_blog_bullet2"] = get_text("main_cmsinfo_blog_bullet2")
    context["textContent_blog_bullet3"] = get_text("main_cmsinfo_blog_bullet3")

    context["textContent_company"] = get_text("main_cmsinfo_company")
    context["textContent_trust"] = get_text("main_cmsinfo_trust")

    context["textContent_stat1"] = get_text("main_cmsinfo_stat1")
    context["textContent_stat2"] = get_text("main_cmsinfo_stat2")
    context["textContent_stat3"] = get_text("main_cmsinfo_stat3")
    context["textContent_stat4"] = get_text("main_cmsinfo_stat4")

    context["textContent_bottomcta"] = get_text("main_cmsinfo_bottomcta")

    context["textContent_company_bullet1"] = get_text("main_cmsinfo_company_bullet1")
    context["textContent_company_bullet2"] = get_text("main_cmsinfo_company_bullet2")
    context["textContent_company_bullet3"] = get_text("main_cmsinfo_company_bullet3")
    context["textContent_company_bullet4"] = get_text("main_cmsinfo_company_bullet4")

    context["image_shot_dashboard"] = get_image("main_cmsinfo_shot_dashboard")
    context["image_sec1_preview_1"] = get_image("main_cmsinfo_sec1_preview_1")
    context["image_sec1_preview_2"] = get_image("main_cmsinfo_sec1_preview_2")
    context["image_sec1_preview_3"] = get_image("main_cmsinfo_sec1_preview_3")
    context["image_sec1_preview_4"] = get_image("main_cmsinfo_sec1_preview_4")
    context["image_sec2_preview_1"] = get_image("main_cmsinfo_sec2_preview_1")
    context["image_sec2_preview_2"] = get_image("main_cmsinfo_sec2_preview_2")
    context["image_sec2_preview_3"] = get_image("main_cmsinfo_sec2_preview_3")
    context["image_blog"] = get_image("main_cmsinfo_blog_image")
    context["image_company"] = get_image("main_cmsinfo_company_image")

    # CMS-verwaltbare Buttons (pro Slot der höchstplatzierte). Fehlt einer,
    # rendert das Template seinen bisherigen Fallback-Link.
    def get_button(place):
        return Button.objects.filter(place=place).order_by("order", "id").first()
    context["cmsinfo_btn_hero"] = get_button("main_cmsinfo_hero_cta")
    context["cmsinfo_btn_demo"] = get_button("main_cmsinfo_demo_cta")
    context["cmsinfo_btn_products"] = get_button("main_cmsinfo_products_cta")
    context["cmsinfo_btn_bottomcta"] = get_button("main_cmsinfo_bottomcta")

    return render(request, 'pages/cmsinfo.html', context=context)


def leistungen_view(request):
    context = {}
    context.update(get_opening_hours())
    logo_slot_keys = [
        "main_leistungen_logo_1",
        "main_leistungen_logo_2",
        "main_leistungen_logo_3",
        "main_leistungen_logo_4",
    ]

    def get_text(name: str):
        return TextContent.objects.filter(name=name).first()

    def get_image(place: str):
        return fileentry.objects.filter(place=place).first()

    legacy_logo_image = get_image("main_leistungen_logos_image")

    context["textContent_intro"] = get_text("main_leistungen_intro")
    context["textContent_cms"] = get_text("main_leistungen_cms")
    context["textContent_webdesign"] = get_text("main_leistungen_webdesign")
    context["textContent_logos"] = get_text("main_leistungen_logos")
    context["textContent_custom"] = get_text("main_leistungen_custom")

    context["image_cms"] = get_image("main_leistungen_cms_image")
    context["image_webdesign"] = get_image("main_leistungen_webdesign_image")
    context["image_logo_1"] = get_image(logo_slot_keys[0]) or legacy_logo_image
    context["image_logo_2"] = get_image(logo_slot_keys[1])
    context["image_logo_3"] = get_image(logo_slot_keys[2])
    context["image_logo_4"] = get_image(logo_slot_keys[3])
    context["image_custom"] = get_image("main_leistungen_custom_image")

    context["textContent_visitenkarten"] = get_text("main_leistungen_visitenkarten")
    context["image_vk_1"] = get_image("main_leistungen_vk_1")
    context["image_vk_2"] = get_image("main_leistungen_vk_2")
    context["image_vk_3"] = get_image("main_leistungen_vk_3")
    context["image_vk_4"] = get_image("main_leistungen_vk_4")

    context["textContent_medien"] = get_text("main_leistungen_medien")
    context["image_medien"] = get_image("main_leistungen_medien_image")

    return render(request, 'pages/leistungen.html', context=context)


def datenschutz_view(request):
    activate(get_language_from_request(request))
    owner_data = WebsiteSettings.get_site_owner()
    policy = PrivacyPolicy.objects.first()
    privacy_content_html = ""
    use_policy = policy is not None

    if policy:
        if policy.use_html and policy.content_html.strip():
            privacy_content_html = policy.render_content(owner_data)
        elif policy.content_text.strip():
            privacy_content_html = policy.render_content(owner_data)

    return render(
        request,
        'pages/datenschutz.html',
        {
            'privacy_content_html': privacy_content_html,
            'use_policy': use_policy,
            'owner_data': owner_data,
        },
    )


def impressum_view(request):
    owner_data = WebsiteSettings.get_site_owner()
    blocks = []
    for block in ImpressumBlock.objects.filter(active=True):
        blocks.append({"title": block.title, "html": block.render_html(owner_data)})

    return render(
        request,
        'pages/impressum.html',
        {
            'owner_data': owner_data,
            'impressum_blocks': blocks,
        },
    )


def cookies_view(request):
    context = {}
    context.update(get_opening_hours())

    def get_text(name: str):
        return TextContent.objects.filter(name=name).first()

    # Hero
    context["textContent_hero"] = get_text("main_cookies_hero")
    # Kategorie-Karten
    context["textContent_necessary"] = get_text("main_cookies_necessary")
    context["textContent_analytics"] = get_text("main_cookies_analytics")
    context["textContent_external"] = get_text("main_cookies_external")
    # Buttons + Hinweis
    context["textContent_actions"] = get_text("main_cookies_actions")
    context["textContent_hinweis"] = get_text("main_cookies_hinweis")

    return render(request, 'pages/cookies.html', context=context)


from .forms import ContactForm
def kontaktform(request):
    success = False
    if request.method == 'POST':
        form = ContactForm(request.POST)
        if form.is_valid():
            # Hier Nachricht verarbeiten und speichern
            Message.objects.create(
                name=form.cleaned_data['name'],
                email=form.cleaned_data['email'],
                title=form.cleaned_data['title'],
                message=form.cleaned_data['message'],
            )
            success = True
    else:
        form = ContactForm()

    def get_text(name: str):
        return TextContent.objects.filter(name=name).first()

    context = {
        'form': form,
        'success': success,
        'recaptcha_public_key': settings.RECAPTCHA_PUBLIC_KEY,
        'google_maps_embed_api_key': settings.GOOGLE_MAPS_EMBED_API_KEY,
        'owner_data': WebsiteSettings.get_site_owner(),
    }
    context.update(get_opening_hours())

    # Hero
    context['textContent_hero'] = get_text('main_kontakt_hero')
    # Info-Panel (links)
    context['textContent_panel'] = get_text('main_kontakt_panel')
    context['textContent_panel_labels'] = get_text('main_kontakt_panel_labels')
    context['textContent_opening_hours'] = get_text('main_kontakt_opening_hours')
    context['textContent_response'] = get_text('main_kontakt_response')
    # Formular (rechts)
    context['textContent_form'] = get_text('main_kontakt_form')
    context['textContent_fields'] = get_text('main_kontakt_fields')
    context['textContent_message_placeholder'] = get_text('main_kontakt_message_placeholder')
    # Erfolgsmeldung
    context['textContent_success'] = get_text('main_kontakt_success')

    return render(request, 'pages/kontakt.html', context)

# Authentication
