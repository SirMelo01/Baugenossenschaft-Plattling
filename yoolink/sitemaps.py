from django.contrib.sitemaps import Sitemap
from django.shortcuts import reverse
from django.utils import timezone
from yoolink.ycms.applications.content.models import Customer
from yoolink.ycms.applications.shop.models import Product
from yoolink.ycms.models import Blog
#from django.urls import reverse
from django.utils.translation import get_language

class StaticViewSitemap(Sitemap):
    changefreq = "daily"
    def items(self):
        return [
            'home',
            'impressum', 'datenschutz', 'cookies', 
            'kunden', 'kontakt', 'leistungen', 'leistungen_cms', 'leistungen_logos', 'leistungen_visitenkarte', 'leistungen_medien', 'leistungen_webdesign',
            'webdesign_deggendorf',
            'blog:blog'
            ]
    
    def lastmod(self, item):
            return timezone.now()
    
    def location(self, item):
        return reverse(item)
    
class BlogSitemap(Sitemap):
    changefreq = "weekly"

    def items(self):
        lang = get_language() or 'de'
        return Blog.objects.filter(active=True, language=lang).order_by('-last_updated')

    def lastmod(self, obj):
        return obj.last_updated
     
class ProductSitemap(Sitemap):
     changefreq = "weekly"
     def items(self):
          return Product.objects.filter(is_active=True)

     def lastmod(self, obj):
          return obj.updated_at


class CustomerSitemap(Sitemap):
    changefreq = "monthly"

    def items(self):
        return Customer.objects.filter(active=True, show_detail_page=True)

    def lastmod(self, obj):
        return obj.updated_at

    def location(self, obj):
        return reverse("kunde-detail", kwargs={"slug": obj.slug})
