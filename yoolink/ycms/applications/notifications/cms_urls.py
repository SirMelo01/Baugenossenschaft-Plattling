from django.urls import path

from . import views
from yoolink.ycms.permissions import cms_permission_required

notifications_required = cms_permission_required("notifications.view")

urlpatterns = [
    path("", notifications_required(views.notifications_list), name="notifications-list"),
    path("mark-all-read/", notifications_required(views.notifications_mark_all_read), name="notifications-mark-all-read"),
    path("spam/", notifications_required(views.notifications_spam_list), name="notifications-spam-list"),
    path("spam/delete-all/", notifications_required(views.notifications_spam_delete_all), name="notifications-spam-delete-all"),
    path("<int:pk>/mark-spam/", notifications_required(views.notification_mark_spam), name="notification-mark-spam"),
    path("<int:pk>/mark-ham/", notifications_required(views.notification_mark_ham), name="notification-mark-ham"),
    path("<int:pk>/mark-read/", notifications_required(views.notification_mark_read), name="notification-mark-read"),
    path("<int:pk>/", notifications_required(views.notification_detail), name="notification-detail"),
    path("<int:pk>/delete/", notifications_required(views.notification_delete), name="notification-delete"),
]
