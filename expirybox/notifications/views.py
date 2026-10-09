from django.contrib import messages
from django.http import JsonResponse
from django.utils.timesince import timesince
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from items.models import Item

from .forms import ReminderForm
from .models import Notification, Reminder


@login_required
def notification_list(request):
    show = request.GET.get("show", "all")
    notes = request.user.notifications.select_related("item", "order")
    if show == "unread":
        notes = notes.filter(is_read=False)
    return render(request, "notifications/list.html", {"notes": notes[:100], "show": show})


@login_required
def notification_open(request, pk):
    note = get_object_or_404(Notification, pk=pk, user=request.user)
    if not note.is_read:
        note.is_read = True
        note.save(update_fields=["is_read"])
    return redirect(note.target_url or "notifications:list")


@login_required
@require_POST
def mark_all_read(request):
    request.user.notifications.filter(is_read=False).update(is_read=True)
    messages.success(request, "All notifications marked as read.")
    return redirect("notifications:list")


@login_required
@require_POST
def notification_delete(request, pk):
    get_object_or_404(Notification, pk=pk, user=request.user).delete()
    return redirect("notifications:list")


@login_required
@require_POST
def reminder_add(request, item_pk):
    item = get_object_or_404(Item, pk=item_pk, user=request.user)
    form = ReminderForm(request.POST, item=item)
    if form.is_valid():
        reminder = form.save(commit=False)
        reminder.item = item
        reminder.reminder_type = Reminder.Type.CUSTOM
        reminder.save()
        messages.success(request, f"Reminder set for {reminder.reminder_date:%b} {reminder.reminder_date.day}.")
    else:
        messages.error(request, " ".join(form.errors.get("reminder_date", ["Check the date."])))
    return redirect(item)


@login_required
@require_POST
def reminder_delete(request, pk):
    reminder = get_object_or_404(Reminder, pk=pk, item__user=request.user)
    item = reminder.item
    reminder.delete()
    messages.success(request, "Reminder removed.")
    nxt = request.POST.get("next")
    if nxt and url_has_allowed_host_and_scheme(nxt, {request.get_host()}):
        return redirect(nxt)
    return redirect(item)


TYPE_TITLES = {
    Notification.Type.EXPIRY: "Expiring soon",
    Notification.Type.EXPIRED: "Item expired",
    Notification.Type.ORDER: "Order update",
    Notification.Type.PAYMENT: "Payment",
    Notification.Type.REVIEW: "New review",
    Notification.Type.SYSTEM: "ExpiryBox",
}


@login_required
def notification_feed(request):
    """JSON feed polled by the page to show new notifications as pop-ups.

    ?after=<id> returns unread notifications newer than that id (max 5, oldest first).
    """
    try:
        after = int(request.GET.get("after", 0))
    except ValueError:
        after = 0
    notes = request.user.notifications.filter(is_read=False, pk__gt=after).order_by("-pk")[:5]
    items = [
        {
            "id": n.pk,
            "type": n.notification_type,
            "title": TYPE_TITLES.get(n.notification_type, "ExpiryBox"),
            "message": n.message,
            "url": reverse("notifications:open", args=[n.pk]),
            "time": f"{timesince(n.created_at).split(',')[0]} ago",
        }
        for n in reversed(list(notes))
    ]
    return JsonResponse({
        "unread": request.user.notifications.filter(is_read=False).count(),
        "items": items,
    })
