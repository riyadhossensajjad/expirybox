from django.urls import path

from . import views

app_name = "marketplace"

urlpatterns = [
    path("", views.browse, name="browse"),
    path("listing/<int:pk>/", views.listing_detail, name="listing_detail"),
    path("listing/<int:pk>/edit/", views.listing_edit, name="listing_edit"),
    path("listing/<int:pk>/publish/", views.listing_publish, name="listing_publish"),
    path("listing/<int:pk>/cancel/", views.listing_cancel, name="listing_cancel"),
    path("sell/<int:item_pk>/", views.listing_create, name="listing_create"),
    path("selling/", views.selling, name="selling"),
    path("orders/", views.buying, name="buying"),
    path("orders/<int:pk>/", views.order_detail, name="order_detail"),
    path("orders/<int:pk>/pay/", views.order_pay, name="order_pay"),
    path("orders/<int:pk>/review/", views.review_create, name="review_create"),
    path("orders/<int:pk>/<str:action>/", views.order_action, name="order_action"),
]
