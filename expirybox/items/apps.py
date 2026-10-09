from django.apps import AppConfig


class ItemsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "items"

    def ready(self):
        _cache_versioned_static_files()


def _cache_versioned_static_files():
    """Performance (development server only): let the browser keep static files.

    CSS/JS are linked with a ?v=<last-modified> stamp (the {% asset %} tag), so a
    changed file always gets a new URL. That makes it safe to tell the browser to
    keep them for a year instead of re-checking every file on every page change.
    Font files never change, so they are cached the same way.
    """
    from django.conf import settings

    if not settings.DEBUG:
        return
    from django.contrib.staticfiles import handlers

    original = handlers.StaticFilesHandlerMixin.serve
    if getattr(original, "_shelflife_cached", False):
        return
    fonts_prefix = "/" + settings.STATIC_URL.strip("/") + "/fonts/"

    def serve(self, request):
        response = original(self, request)
        if response.status_code == 200 and (request.GET.get("v") or request.path.startswith(fonts_prefix)):
            response["Cache-Control"] = "public, max-age=31536000, immutable"
        return response

    serve._shelflife_cached = True
    handlers.StaticFilesHandlerMixin.serve = serve
