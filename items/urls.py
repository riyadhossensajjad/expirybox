from django.urls import path

from . import views

app_name = "items"

urlpatterns = [
    path("dashboard/", views.dashboard, name="dashboard"),
    path("", views.item_list, name="list"),
    path("suggest/", views.item_suggest, name="suggest"),
    path("new/", views.item_create, name="create"),
    path("<int:pk>/", views.item_detail, name="detail"),
    path("<int:pk>/edit/", views.item_update, name="update"),
    path("<int:pk>/delete/", views.item_delete, name="delete"),
    path("<int:pk>/used/", views.item_mark_used, name="mark_used"),
    path("<int:pk>/qr.svg", views.item_qr, name="qr"),
]
