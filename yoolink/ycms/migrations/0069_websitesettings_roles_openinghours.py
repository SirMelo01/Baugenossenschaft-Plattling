from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import yoolink.ycms.models


OWNER_PERMISSIONS = [
    "dashboard.view",
    "pages.edit",
    "blog.edit",
    "media.edit",
    "buttons.edit",
    "shop.view",
    "products.edit",
    "orders.edit",
    "team.edit",
    "pricing.edit",
    "faq.edit",
    "opening_hours.edit",
    "notifications.view",
    "website_settings.edit",
    "security.edit",
    "developer.manage",
    "users.manage",
    "roles.manage",
]

SYSTEM_ROLES = {
    "owner": {"name": "OWNER", "permissions": OWNER_PERMISSIONS},
    "editor": {
        "name": "EDITOR",
        "permissions": [
            "dashboard.view",
            "pages.edit",
            "blog.edit",
            "media.edit",
            "buttons.edit",
            "faq.edit",
            "notifications.view",
            "security.edit",
        ],
    },
    "shop-manager": {
        "name": "SHOP MANAGER",
        "permissions": [
            "dashboard.view",
            "shop.view",
            "products.edit",
            "orders.edit",
            "media.edit",
            "notifications.view",
            "security.edit",
        ],
    },
    "developer": {
        "name": "DEVELOPER",
        "permissions": [
            "dashboard.view",
            "developer.manage",
            "notifications.view",
            "security.edit",
        ],
    },
    "viewer": {
        "name": "VIEWER",
        "permissions": [
            "dashboard.view",
            "notifications.view",
            "security.edit",
        ],
    },
}


PUBLIC_FIELDS = [
    "company_name",
    "tel_number",
    "fax_number",
    "mobile_number",
    "website",
    "address",
    "social_instagram",
    "social_x",
    "social_facebook",
    "social_linkedin",
    "price_range",
    "area_served",
    "business_description",
    "address_region",
    "address_country",
    "geo_latitude",
    "geo_longitude",
    "vacation",
    "vacationText",
    "vacationText_de",
    "vacationText_en",
    "vacation_start",
    "vacation_end",
    "global_font",
    "logo",
    "favicon",
]


def seed_settings_roles_and_opening_hours(apps, schema_editor):
    WebsiteSettings = apps.get_model("ycms", "WebsiteSettings")
    UserSettings = apps.get_model("ycms", "UserSettings")
    OpeningHours = apps.get_model("ycms", "OpeningHours")
    CMSRole = apps.get_model("ycms", "CMSRole")
    CMSUserRole = apps.get_model("ycms", "CMSUserRole")
    User = apps.get_model("users", "User")

    owner_settings = (
        UserSettings.objects.select_related("user")
        .filter(user__is_staff=False)
        .order_by("id")
        .first()
    ) or UserSettings.objects.select_related("user").order_by("id").first()

    website_settings = WebsiteSettings.objects.order_by("id").first()
    if not website_settings:
        website_settings = WebsiteSettings.objects.create()

    if owner_settings:
        for field in PUBLIC_FIELDS:
            if hasattr(owner_settings, field) and hasattr(website_settings, field):
                setattr(website_settings, field, getattr(owner_settings, field))
        if hasattr(owner_settings, "email"):
            website_settings.contact_email = owner_settings.email or ""
        website_settings.save()

    for opening_hours in OpeningHours.objects.all():
        opening_hours.website = website_settings
        opening_hours.save(update_fields=["website"])

    roles = {}
    for slug, role_defaults in SYSTEM_ROLES.items():
        role, _created = CMSRole.objects.update_or_create(
            slug=slug,
            defaults={
                "name": role_defaults["name"],
                "permissions": role_defaults["permissions"],
                "is_system": True,
            },
        )
        roles[slug] = role

    owner_role = roles["owner"]
    for user in User.objects.filter(is_active=True):
        CMSUserRole.objects.get_or_create(user=user, role=owner_role)


class Migration(migrations.Migration):

    dependencies = [
        ("ycms", "0068_usersettings_seo_fields"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="WebsiteSettings",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("company_name", models.CharField(blank=True, default="", max_length=255)),
                ("contact_email", models.EmailField(blank=True, default="", max_length=255)),
                ("tel_number", models.CharField(blank=True, default="", max_length=18)),
                ("fax_number", models.CharField(blank=True, default="", max_length=18)),
                ("mobile_number", models.CharField(blank=True, default="", max_length=18)),
                ("website", models.URLField(blank=True, default="")),
                ("address", models.CharField(blank=True, default="", max_length=255)),
                ("social_instagram", models.URLField(blank=True, default="https://www.instagram.com/yoolinkde/")),
                ("social_x", models.URLField(blank=True, default="https://x.com/YooLinkDE")),
                ("social_facebook", models.URLField(blank=True, default="")),
                ("social_linkedin", models.URLField(blank=True, default="")),
                ("price_range", models.CharField(blank=True, default="ab 40 €/Monat", max_length=50)),
                ("area_served", models.CharField(blank=True, default="Passau, Regensburg, Deggendorf, Niederbayern", max_length=255)),
                ("business_description", models.CharField(blank=True, default="Webdesign Agentur im Raum Niederbayern", max_length=255)),
                ("address_region", models.CharField(blank=True, default="Bayern", max_length=100)),
                ("address_country", models.CharField(blank=True, default="DE", max_length=2)),
                ("geo_latitude", models.CharField(blank=True, default="48.7667", max_length=20)),
                ("geo_longitude", models.CharField(blank=True, default="13.0500", max_length=20)),
                ("vacation", models.BooleanField(default=False)),
                ("vacationText", models.TextField(default="Wir sind aktuell im Urlaub. Ab dem XX.XX sind wir wieder für Sie da!")),
                ("vacationText_de", models.TextField(default="Wir sind aktuell im Urlaub. Ab dem XX.XX sind wir wieder für Sie da!", null=True)),
                ("vacationText_en", models.TextField(default="Wir sind aktuell im Urlaub. Ab dem XX.XX sind wir wieder für Sie da!", null=True)),
                ("vacation_start", models.DateTimeField(blank=True, null=True)),
                ("vacation_end", models.DateTimeField(blank=True, null=True)),
                ("global_font", models.CharField(blank=True, default="font-sans", max_length=60)),
                ("logo", models.ImageField(blank=True, default="", upload_to=yoolink.ycms.models.upload_to_website_settings)),
                ("favicon", models.ImageField(blank=True, default="", upload_to=yoolink.ycms.models.upload_to_website_settings)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.CreateModel(
            name="CMSRole",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=80)),
                ("slug", models.SlugField(max_length=90, unique=True)),
                ("description", models.TextField(blank=True, default="")),
                ("permissions", models.JSONField(blank=True, default=list)),
                ("is_system", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["name"]},
        ),
        migrations.CreateModel(
            name="CMSUserRole",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("assigned_at", models.DateTimeField(auto_now_add=True)),
                ("role", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="user_assignments", to="ycms.cmsrole")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="cms_role_assignments", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["user__username", "role__name"], "unique_together": {("user", "role")}},
        ),
        migrations.AddField(
            model_name="usersettings",
            name="must_change_password",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="openinghours",
            name="website",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="opening_hours", to="ycms.websitesettings"),
        ),
        migrations.AlterField(
            model_name="openinghours",
            name="day",
            field=models.CharField(choices=[("MON", "Montag"), ("TUE", "Dienstag"), ("WED", "Mittwoch"), ("THU", "Donnerstag"), ("FRI", "Freitag"), ("SAT", "Samstag"), ("SUN", "Sonntag")], max_length=3),
        ),
        migrations.AlterField(
            model_name="openinghours",
            name="user",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="opening_hours", to=settings.AUTH_USER_MODEL),
        ),
        migrations.RunPython(seed_settings_roles_and_opening_hours, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name="openinghours",
            constraint=models.UniqueConstraint(fields=("website", "day"), name="unique_opening_hours_per_website_day"),
        ),
    ]
