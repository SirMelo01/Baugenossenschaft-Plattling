from django.urls import path

from . import views
from yoolink.ycms.permissions import cms_permission_required

shop_required = cms_permission_required("shop.view")
products_required = cms_permission_required("products.edit")
orders_required = cms_permission_required("orders.edit")

urlpatterns = [
    # CMS shop dashboard
    path("", shop_required(views.shop), name="shop"),
    path("settings/update/", products_required(views.shop_settings_update), name="shop-settings-update"),

    # CMS products
    path("products/", products_required(views.product_view), name="products"),
    path("products/search/", products_required(views.product_search), name="product_search"),
    path("products/create/", products_required(views.product_create_view), name="product-create"),
    path("products/create/upload", products_required(views.product_create), name="product-create-upload"),
    path("products/get_categories/", products_required(views.get_categories), name="get-categories"),
    path("products/get_brands/", products_required(views.get_brands), name="get-brands"),
    path("products/get_groups/", products_required(views.get_groups), name="get-groups"),
    path("products/groups/create/", products_required(views.group_create), name="group-create"),
    path("products/groups/<int:group_id>/move/", products_required(views.group_move), name="group-move"),
    path("products/groups/<int:group_id>/delete/", products_required(views.group_delete), name="group-delete"),
    path("products/description-image/", products_required(views.product_description_image_upload), name="product-description-image"),
    path("products/<int:product_id>/<slug:slug>/", products_required(views.product_detail), name="product-detail"),
    path("products/<int:product_id>/<slug:slug>/update", products_required(views.product_update), name="product-detail-update"),
    path("products/<int:product_id>/<slug:slug>/delete", products_required(views.product_delete), name="product-detail-delete"),

    # CMS orders
    path("orders/", orders_required(views.order_view), name="order-overview"),
    path("orders/filter/", orders_required(views.get_orders), name="order-api"),
    path("orders/<int:order_id>/", orders_required(views.order_detail_view), name="order-detail-view"),
    path("orders/<int:order_id>/update_order_status/", orders_required(views.update_order_status_admin), name="update_order_status"),
    path("orders/<int:order_id>/delete/", orders_required(views.delete_order), name="delete_order"),

    # CMS order API
    path("api/orders/<int:order_id>/", orders_required(views.get_order_by_id), name="get_order_by_id"),

    # CMS reviews
    path("reviews/<int:review_id>/delete_reviews/", orders_required(views.delete_review), name="delete_review"),
]
