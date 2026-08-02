from django.urls import path, include

from .views import Load_Index_Blog, BlogDetailView


app_name = "blog"


urlpatterns = [
    path("", Load_Index_Blog.as_view(), name="blog"),
    path("<int:pk>-<slug:slug_title>/", BlogDetailView.as_view(), name="blog-detail"),
]
