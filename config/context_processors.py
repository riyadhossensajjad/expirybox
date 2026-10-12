from django.conf import settings


def site(request):
    # A one-off success animation queued by a view (e.g. after adding an item).
    celebrate = None
    if hasattr(request, "session") and "celebrate" in request.session:
        celebrate = request.session.pop("celebrate")
    # Entrance animation, played once on the first page after log in / sign up.
    welcome = bool(hasattr(request, "session") and request.session.pop("welcome", False))
    return {
        "SITE_NAME": settings.SITE_NAME,
        "CURRENCY": settings.CURRENCY_SYMBOL,
        "celebrate": celebrate,
        "welcome": welcome,
    }
