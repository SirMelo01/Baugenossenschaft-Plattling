from django.conf import settings
from django.db import migrations


def seed_customer_settings(apps, schema_editor):
    WebsiteSettings = apps.get_model("ycms", "WebsiteSettings")

    settings_obj = WebsiteSettings.objects.order_by("id").first()
    if settings_obj is None:
        settings_obj = WebsiteSettings()

    settings_obj.company_name = "Baugenossenschaft Plattling eG"
    settings_obj.owner_name = "Baugenossenschaft Plattling eG"
    settings_obj.contact_email = "info@baugenossenschaft-plattling.de"
    settings_obj.tel_number = "09931 890073-0"
    settings_obj.fax_number = "09931 890073-9"
    settings_obj.mobile_number = ""
    # Muss zu settings.SITE_DOMAIN passen: Dieser Wert landet in canonical-/OG-URLs
    # und darf deshalb nicht auf eine andere oder weiterleitende Domain zeigen.
    settings_obj.website = f"https://{settings.SITE_DOMAIN}"
    settings_obj.address = "Schillerstr. 6b, 94447 Plattling"
    settings_obj.social_instagram = ""
    settings_obj.social_x = ""
    settings_obj.social_facebook = ""
    settings_obj.social_linkedin = ""
    settings_obj.price_range = ""
    settings_obj.area_served = "Plattling"
    settings_obj.business_description = "Baugenossenschaft für sicheren und bezahlbaren Wohnraum in Plattling"
    settings_obj.site_meta_description = (
        "Die Baugenossenschaft Plattling eG bietet seit 1921 sicheren und bezahlbaren "
        "Wohnraum in Plattling."
    )
    settings_obj.site_meta_author = "Baugenossenschaft Plattling eG"
    settings_obj.address_region = "Bayern"
    settings_obj.address_country = "DE"
    settings_obj.geo_latitude = "48.7786"
    settings_obj.geo_longitude = "12.8756"
    settings_obj.save()


class Migration(migrations.Migration):
    dependencies = [
        ("ycms", "0079_strip_language_suffix_from_blog_slugs"),
    ]

    operations = [
        migrations.RunPython(seed_customer_settings, migrations.RunPython.noop),
    ]
