from django.urls import path

from . import views

app_name = "impact"

urlpatterns = [
    path("", views.overview, name="overview"),
    path("export.pdf", views.export_pdf, name="export_pdf"),
    path("records/<int:pk>/edit/", views.record_edit, name="record_edit"),
]
