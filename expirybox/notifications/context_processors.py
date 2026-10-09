from django.conf import settings


def unread_notifications(request):
    """Data the app shell needs on every page: bell count, popover list, banner."""
    user = request.user
    if not user.is_authenticated:
        return {"unread_count": 0}
    notes = user.notifications.select_related("item", "order")
    latest = notes.values_list("pk", flat=True).first() or 0
    return {
        "unread_count": notes.filter(is_read=False).count(),
        "popover_notes": notes[:6],
        "latest_notification_id": latest,
        "week_expiring_count": user.items.expiring_within(settings.EXPIRING_SOON_DAYS).count(),
    }
