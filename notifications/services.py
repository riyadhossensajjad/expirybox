"""Reminder scheduling, notification delivery and the daily expiry sweep."""
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import Notification, Reminder

OFFSET_TYPES = {
    7: Reminder.Type.WEEK_BEFORE,
    3: Reminder.Type.THREE_DAYS,
    1: Reminder.Type.DAY_BEFORE,
    0: Reminder.Type.ON_EXPIRY,
}


def notify(user, message, notification_type=Notification.Type.SYSTEM, item=None, order=None):
    return Notification.objects.create(
        user=user,
        message=message[:255],
        notification_type=notification_type,
        item=item,
        order=order,
    )


def schedule_reminders(item):
    """(Re)create the automatic reminders for an item from its expiry date.

    Custom reminders the user added are kept; unsent automatic ones are rebuilt
    so that editing the expiry date moves them.
    """
    today = timezone.localdate()
    item.reminders.filter(is_sent=False).exclude(reminder_type=Reminder.Type.CUSTOM).delete()
    if item.expiry_date < today:
        return
    used_dates = set()
    for offset in sorted(settings.REMINDER_OFFSETS_DAYS, reverse=True):
        # A reminder whose slot has already passed fires today instead, so an
        # item added two days before expiry still gets a heads-up right away.
        when = max(item.expiry_date - timedelta(days=offset), today)
        if when in used_dates:
            continue
        used_dates.add(when)
        Reminder.objects.create(
            item=item,
            reminder_date=when,
            reminder_type=OFFSET_TYPES.get(offset, Reminder.Type.CUSTOM),
        )


def _reminder_message(reminder):
    item = reminder.item
    days = (item.expiry_date - timezone.localdate()).days
    if days <= 0:
        when = "today"
    elif days == 1:
        when = "tomorrow"
    else:
        when = f"in {days} days"
    tip = " List it in the shop before it goes to waste." if item.can_be_listed else ""
    return f"{item.item_name} expires {when}.{tip}"


def send_due_reminders(today=None):
    """Turn every due, unsent reminder into a Notification. Returns the count sent."""
    from items.models import ItemStatus

    today = today or timezone.localdate()
    due = (
        Reminder.objects.select_related("item", "item__user")
        .filter(is_sent=False, reminder_date__lte=today)
    )
    sent = 0
    for reminder in due:
        if reminder.item.status in (ItemStatus.ACTIVE, ItemStatus.LISTED):
            notify(
                reminder.item.user,
                _reminder_message(reminder),
                Notification.Type.EXPIRY,
                item=reminder.item,
            )
            sent += 1
        reminder.is_sent = True
        reminder.save(update_fields=["is_sent"])
    return sent


def expire_items(today=None):
    """Mark open items past their expiry date as EXPIRED and log the loss."""
    from impact.services import record_outcome
    from impact.models import OutcomeStatus
    from items.models import Item, ItemStatus
    from marketplace.models import Listing, ListingStatus

    today = today or timezone.localdate()
    count = 0
    for item in Item.objects.open().filter(expiry_date__lt=today).select_related("user"):
        with transaction.atomic():
            lost_value = item.price or 0
            listing = item.listings.filter(status=ListingStatus.ACTIVE).first()
            if listing:
                lost_value = listing.original_price * listing.quantity
            item.listings.filter(status__in=[ListingStatus.ACTIVE, ListingStatus.DRAFT]).update(
                status=ListingStatus.EXPIRED
            )
            item.status = ItemStatus.EXPIRED
            item.save(update_fields=["status", "updated_at"])
            record_outcome(
                item,
                OutcomeStatus.LOST,
                amount=lost_value,
                resolved_date=item.expiry_date,
                notes="Expired before it was used or sold.",
            )
            notify(
                item.user,
                f"{item.item_name} has expired. It's been moved to your impact history.",
                Notification.Type.EXPIRED,
                item=item,
            )
            count += 1

    # Listings whose pickup window closed even though the item itself is still good.
    Listing.objects.filter(status=ListingStatus.ACTIVE, available_until__lt=today).update(
        status=ListingStatus.EXPIRED
    )
    return count


def run_sweep(today=None):
    return {
        "reminders_sent": send_due_reminders(today),
        "items_expired": expire_items(today),
    }
