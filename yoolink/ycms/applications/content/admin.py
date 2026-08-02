from django.contrib import admin

from .models import Customer, PrivacyPolicy, ServiceLocation, TextContent


admin.site.register(TextContent)
admin.site.register(PrivacyPolicy)


@admin.register(ServiceLocation)
class ServiceLocationAdmin(admin.ModelAdmin):
    list_display = ("name", "url", "latitude", "longitude", "is_headquarters", "active", "order")
    list_filter = ("active", "is_headquarters")
    search_fields = ("name", "url")


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ("name", "section", "active", "show_detail_page", "order", "published_date")
    list_filter = ("section", "active", "show_detail_page")
    search_fields = ("name", "website_url", "website_display")
    prepopulated_fields = {"slug": ("name",)}

