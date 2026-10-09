from django.urls import path

from . import views

app_name = "notifications"

urlpatterns = [
    path("", views.notification_list, name="list"),
    path("feed/", views.notification_feed, name="feed"),
    path("<int:pk>/open/", views.notification_open, name="open"),
    path("<int:pk>/delete/", views.notification_delete, name="delete"),
    path("read-all/", views.mark_all_read, name="mark_all_read"),
    path("reminders/add/<int:item_pk>/", views.reminder_add, name="reminder_add"),
    path("reminders/<int:pk>/delete/", views.reminder_delete, name="reminder_delete"),
]
