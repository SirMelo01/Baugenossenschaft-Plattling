from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ycms", "0067_fileentry_mobile_file"),
    ]

    operations = [
        migrations.AddField(
            model_name="usersettings",
            name="social_instagram",
            field=models.URLField(blank=True, default="https://www.instagram.com/yoolinkde/"),
        ),
        migrations.AddField(
            model_name="usersettings",
            name="social_x",
            field=models.URLField(blank=True, default="https://x.com/YooLinkDE"),
        ),
        migrations.AddField(
            model_name="usersettings",
            name="social_facebook",
            field=models.URLField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="usersettings",
            name="social_linkedin",
            field=models.URLField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="usersettings",
            name="price_range",
            field=models.CharField(blank=True, default="ab 40 €/Monat", max_length=50),
        ),
        migrations.AddField(
            model_name="usersettings",
            name="area_served",
            field=models.CharField(
                blank=True,
                default="Passau, Regensburg, Deggendorf, Niederbayern",
                max_length=255,
            ),
        ),
        migrations.AddField(
            model_name="usersettings",
            name="business_description",
            field=models.CharField(
                blank=True,
                default="Webdesign Agentur im Raum Niederbayern",
                max_length=255,
            ),
        ),
        migrations.AddField(
            model_name="usersettings",
            name="address_region",
            field=models.CharField(blank=True, default="Bayern", max_length=100),
        ),
        migrations.AddField(
            model_name="usersettings",
            name="address_country",
            field=models.CharField(blank=True, default="DE", max_length=2),
        ),
        migrations.AddField(
            model_name="usersettings",
            name="geo_latitude",
            field=models.CharField(blank=True, default="48.7667", max_length=20),
        ),
        migrations.AddField(
            model_name="usersettings",
            name="geo_longitude",
            field=models.CharField(blank=True, default="13.0500", max_length=20),
        ),
    ]
