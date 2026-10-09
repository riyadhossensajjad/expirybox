from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from items.views import home

admin.site.site_header = "ExpiryBox admin"
admin.site.site_title = "ExpiryBox"

urlpatterns = [
    path("", home, name="home"),
    path("accounts/", include("accounts.urls")),
    path("items/", include("items.urls")),
    path("notifications/", include("notifications.urls")),
    path("impact/", include("impact.urls")),
    path("market/", include("marketplace.urls")),
    path("admin/", admin.site.urls),
    path("files/", include("filestore.urls")),   # photos stored in the database (on Vercel)
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
