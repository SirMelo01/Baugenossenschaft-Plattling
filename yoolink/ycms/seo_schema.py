"""Site-wide SEO structured data (JSON-LD).

Builds the Organization + WebSite + LocalBusiness ``@graph`` that is rendered on
every public page (see ``base.html``). Scalar NAP values (name, e-mail, phone,
street, logo) are pulled from the CMS site-owner record (``WebsiteSettings``) so they
stay editable in the CMS, with safe fallbacks so the markup is never empty/broken.

This module deliberately has no Django imports so it can be unit-tested in
isolation: it only reads attributes off the passed-in ``owner`` object.
"""

import json
import re

SITE_BASE_URL = "https://yoolink.de"

# Static fallbacks (legally correct NAP per the Impressum) used when the CMS
# field is empty. Postal code / city / region live here because the CMS only
# stores a single free-text address field today.
_FALLBACK_NAME = "YooLink"
_FALLBACK_EMAIL = "info@yoolink.de"
_FALLBACK_PHONE = "+49 170 5977862"
_FALLBACK_STREET = "Schanzenweg 53"
_POSTAL_CODE = "94469"
_LOCALITY = "Deggendorf"
_REGION = "Bayern"
_COUNTRY = "DE"
_GEO_LAT = 48.7667  # Deggendorf (registered business location)
_GEO_LNG = 13.0500
_OWNER_PERSON = "Sebastian Rauch"

_PRICE_RANGE = "ab 40 €/Monat"
_DESCRIPTION = "Webdesign Agentur im Raum Niederbayern"

# Defaults used only when the corresponding CMS field is empty.
_AREA_SERVED_DEFAULT = ["Passau", "Regensburg", "Deggendorf", "Niederbayern"]
_SAME_AS_DEFAULT = [
    "https://www.instagram.com/yoolinkde/",
    "https://x.com/YooLinkDE",
]


def _field(owner, attr, fallback):
    """Return a stripped CMS string field, or the fallback when empty/missing."""
    value = getattr(owner, attr, "") if owner else ""
    if isinstance(value, str):
        value = value.strip()
    return value or fallback


def _normalize_phone(raw, fallback):
    """Return an international-format phone number (e.g. +491705977862).

    The CMS often stores the national format (0170...); schema.org/Google prefer
    the international E.164-style form.
    """
    raw = (raw or "").strip() or fallback
    digits = re.sub(r"[^\d+]", "", raw)
    if digits.startswith("+"):
        return digits
    if digits.startswith("00"):
        return "+" + digits[2:]
    if digits.startswith("0"):
        return "+49" + digits[1:]
    return digits or fallback


def _parse_address(raw, fb_street, fb_plz, fb_city):
    """Split a single free-text address into (street, postal_code, city).

    Handles both common German orderings, e.g. "Am Altbach 6, 94491 Hengersberg"
    and "94491 Hengersberg, Am Altbach 6". Falls back to the given defaults when a
    part cannot be determined, so the structured address is never broken/duplicated.
    """
    raw = (raw or "").strip()
    if not raw:
        return fb_street, fb_plz, fb_city
    m = re.search(r"(\d{5})\s+([^\d,]+)", raw)  # postal code + city
    if not m:
        return raw, fb_plz, fb_city  # no postal code found -> treat all as street
    plz = m.group(1)
    city = m.group(2).strip(" ,")
    street = re.sub(r"\s+", " ", raw[: m.start()] + " " + raw[m.end():]).strip(" ,")
    return (street or fb_street), plz, (city or fb_city)


def _logo_url(owner):
    """Absolute logo URL: CMS-uploaded logo if present, else the static OG image."""
    url = ""
    try:
        if owner and getattr(owner, "logo", None):
            url = owner.logo.url or ""
    except Exception:
        url = ""
    if not url:
        return f"{SITE_BASE_URL}/static/images/og-preview.png"
    if url.startswith("/"):
        return f"{SITE_BASE_URL}{url}"
    return url


def _same_as(owner):
    """Collect non-empty social profile URLs; fall back to defaults if none set."""
    urls = [
        _field(owner, "social_instagram", ""),
        _field(owner, "social_x", ""),
        _field(owner, "social_facebook", ""),
        _field(owner, "social_linkedin", ""),
    ]
    urls = [u for u in urls if u]
    return urls or list(_SAME_AS_DEFAULT)


def _area_served(owner):
    """Comma-separated CMS field -> list of place names; default if empty."""
    raw = _field(owner, "area_served", "")
    items = [a.strip() for a in raw.split(",") if a.strip()]
    return items or list(_AREA_SERVED_DEFAULT)


def _geo(owner):
    """GeoCoordinates dict from the CMS lat/lng fields (falls back to defaults)."""

    def num(attr, fallback):
        try:
            return float(str(_field(owner, attr, "")).replace(",", "."))
        except (TypeError, ValueError):
            return fallback

    return {
        "@type": "GeoCoordinates",
        "latitude": num("geo_latitude", _GEO_LAT),
        "longitude": num("geo_longitude", _GEO_LNG),
    }


def build_site_schema_jsonld(owner):
    """Build the site-wide JSON-LD string, safe to embed inside a <script> tag."""
    name = _field(owner, "company_name", _FALLBACK_NAME)
    email = _field(owner, "email", _FALLBACK_EMAIL)
    raw_phone = _field(owner, "tel_number", "") or _field(owner, "mobile_number", "")
    telephone = _normalize_phone(raw_phone, _FALLBACK_PHONE)
    street, postal_code, locality = _parse_address(
        _field(owner, "address", ""), _FALLBACK_STREET, _POSTAL_CODE, _LOCALITY
    )
    founder_name = _field(owner, "owner_name", _OWNER_PERSON)
    legal_name = f"{name} – Inhaber {founder_name}"
    price_range = _field(owner, "price_range", _PRICE_RANGE)
    description = _field(owner, "site_meta_description", "") or _field(owner, "business_description", _DESCRIPTION)
    region = _field(owner, "address_region", _REGION)
    country = _field(owner, "address_country", _COUNTRY)
    same_as = _same_as(owner)
    logo_url = _logo_url(owner)
    org_id = f"{SITE_BASE_URL}/#organization"

    graph = {
        "@context": "https://schema.org",
        "@graph": [
            {
                "@type": "Organization",
                "@id": org_id,
                "name": name,
                "legalName": legal_name,
                "url": f"{SITE_BASE_URL}/",
                "email": email,
                "telephone": telephone,
                "founder": {"@type": "Person", "name": founder_name},
                "logo": {"@type": "ImageObject", "url": logo_url},
                "image": logo_url,
                "sameAs": same_as,
            },
            {
                "@type": "WebSite",
                "@id": f"{SITE_BASE_URL}/#website",
                "url": f"{SITE_BASE_URL}/",
                "name": name,
                "description": description,
                "publisher": {"@id": org_id},
                "inLanguage": "de-DE",
            },
            {
                "@type": ["ProfessionalService", "LocalBusiness"],
                "@id": f"{SITE_BASE_URL}/#localbusiness",
                "name": name,
                "url": f"{SITE_BASE_URL}/",
                "image": logo_url,
                "email": email,
                "telephone": telephone,
                "priceRange": price_range,
                "description": description,
                "parentOrganization": {"@id": org_id},
                "address": {
                    "@type": "PostalAddress",
                    "streetAddress": street,
                    "postalCode": postal_code,
                    "addressLocality": locality,
                    "addressRegion": region,
                    "addressCountry": country,
                },
                "geo": _geo(owner),
                "areaServed": _area_served(owner),
                "sameAs": same_as,
            },
        ],
    }

    payload = json.dumps(graph, ensure_ascii=False)
    # Neutralise characters that could break out of the surrounding <script>.
    return (
        payload.replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
    )
