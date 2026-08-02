from django.urls import path

from . import views

urlpatterns = [
    # Public product API
    path("products/search/", views.search_products, name="product-client-search"),

    # Public cart and checkout
    path("cart/", views.cart_view, name="cart"),
    path("cart/verify/success/", views.cart_verify_success_view, name="cart-verify-success"),
    path("order/verify/", views.order_verify_view, name="order-verify"),
    path("order/verify/success/", views.order_verify_success_view, name="order-verify-success"),

    path("api/cart/", views.cart_items, name="api-cart"),
    path("api/cart/update/", views.update_cart_items, name="api-cart-update"),
    path("api/cart/verify/", views.verify_cart, name="api-cart-verify"),
    path("api/cart/add/<int:product_id>/", views.add_to_cart, name="api-cart-add"),
    path("api/cart/<int:order_item_id>/remove/", views.remove_from_cart, name="api-cart-remove"),
    path("api/cart/<int:order_item_id>/update-quantity/", views.update_quantity, name="api-cart-update-quantity"),
    path("api/order/verify/", views.verify_order, name="api-order-verify"),
]