from django.urls import path

from . import views

urlpatterns = [
    # Shop urls
    path("", views.public_shop, name="products"),
    path("<int:product_id>-<slug:slug>", view=views.detail, name="product-detail"),
]