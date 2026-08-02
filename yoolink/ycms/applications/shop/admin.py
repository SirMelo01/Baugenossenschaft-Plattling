from django.contrib import admin

from yoolink.ycms.applications.shop.models import Brand, Category, Order, OrderItem, Product, Review, ShippingAddress

# Register your models here.
admin.site.register(Product)
admin.site.register(Category)
admin.site.register(Brand)
admin.site.register(OrderItem)
admin.site.register(Review)
admin.site.register(ShippingAddress)
admin.site.register(Order)
