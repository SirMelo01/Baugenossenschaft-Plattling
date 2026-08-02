from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("cms_content", "0001_initial"),
        ("ycms", "0066_move_page_content_to_content_app"),
    ]

    operations = [
        migrations.CreateModel(
            name="Customer",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(default="", max_length=160)),
                ("subtitle", models.CharField(blank=True, default="", max_length=200)),
                ("subtitle_de", models.CharField(blank=True, default="", max_length=200, null=True)),
                ("subtitle_en", models.CharField(blank=True, default="", max_length=200, null=True)),
                ("slug", models.SlugField(blank=True, max_length=180, unique=True)),
                ("website_url", models.URLField(blank=True, default="")),
                ("website_display", models.CharField(blank=True, default="", max_length=200)),
                ("published_date", models.DateField(blank=True, null=True)),
                (
                    "section",
                    models.CharField(
                        choices=[
                            ("references", "Referenzen / Kunden"),
                            ("special", "Spezielle Programmierungen"),
                        ],
                        default="references",
                        max_length=20,
                    ),
                ),
                ("short_description", models.TextField(blank=True, default="")),
                ("short_description_de", models.TextField(blank=True, default="", null=True)),
                ("short_description_en", models.TextField(blank=True, default="", null=True)),
                ("description", models.TextField(blank=True, default="")),
                ("description_de", models.TextField(blank=True, default="", null=True)),
                ("description_en", models.TextField(blank=True, default="", null=True)),
                ("services_text", models.TextField(blank=True, default="")),
                ("services_text_de", models.TextField(blank=True, default="", null=True)),
                ("services_text_en", models.TextField(blank=True, default="", null=True)),
                ("testimonial", models.TextField(blank=True, default="")),
                ("testimonial_de", models.TextField(blank=True, default="", null=True)),
                ("testimonial_en", models.TextField(blank=True, default="", null=True)),
                ("testimonial_author", models.CharField(blank=True, default="", max_length=160)),
                ("testimonial_author_de", models.CharField(blank=True, default="", max_length=160, null=True)),
                ("testimonial_author_en", models.CharField(blank=True, default="", max_length=160, null=True)),
                (
                    "logo_style",
                    models.CharField(
                        choices=[
                            ("circle", "Logo rund"),
                            ("square", "Logo quadratisch"),
                            ("text", "Nur Text/Initialen (kein Logo)"),
                        ],
                        default="circle",
                        max_length=10,
                    ),
                ),
                ("logo_fallback_text", models.CharField(blank=True, default="", max_length=8)),
                ("active", models.BooleanField(default=True)),
                ("show_detail_page", models.BooleanField(default=True)),
                ("order", models.PositiveIntegerField(db_index=True, default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "title_image",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=models.deletion.SET_NULL,
                        related_name="customer_title_images",
                        to="ycms.fileentry",
                    ),
                ),
                (
                    "banner_image",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=models.deletion.SET_NULL,
                        related_name="customer_banner_images",
                        to="ycms.fileentry",
                    ),
                ),
                (
                    "logo",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=models.deletion.SET_NULL,
                        related_name="customer_logos",
                        to="ycms.fileentry",
                    ),
                ),
                (
                    "gallery",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=models.deletion.SET_NULL,
                        related_name="customers",
                        to="ycms.galerie",
                    ),
                ),
            ],
            options={
                "db_table": "ycms_customer",
                "ordering": ["order", "-published_date", "id"],
            },
        ),
    ]
