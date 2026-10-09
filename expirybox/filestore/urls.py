from django.urls import path

from . import views

app_name = "filestore"
urlpatterns = [path("<path:name>", views.serve, name="file")]
