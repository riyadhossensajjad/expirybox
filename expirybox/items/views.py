from django.conf import settings
from django.contrib import messages
from django.db.models import Case, IntegerField, Value, When
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.db.models import Exists, OuterRef, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from impact.models import OutcomeStatus
from impact.services import record_outcome
from marketplace.models import Listing, Order, OrderStatus
from notifications.forms import ReminderForm
from notifications.services import schedule_reminders

from .forms import ItemForm, MarkUsedForm
from .models import Category, Item, ItemStatus


def home(request):
    if request.user.is_authenticated:
        return redirect("items:dashboard")
    fresh_listings = Listing.objects.live().select_related("item", "item__category", "seller")[:8]
    return render(request, "home.html", {"listings": fresh_listings, "phone_listings": fresh_listings[:5]})


@login_required
def dashboard(request):
    user = request.user
    soon = settings.EXPIRING_SOON_DAYS
    open_items = user.items.open().select_related("category")
    expiring = open_items.expiring_within(soon)
    year = timezone.localdate().year
    summary = user.impact_summaries.filter(year=year).first()
    seller_queue = Order.objects.filter(
        listing__seller=user, status__in=[OrderStatus.PENDING, OrderStatus.PAID]
    ).select_related("listing__item", "buyer")[:5]

    hour = timezone.localtime().hour
    greeting = "Good morning" if hour < 12 else "Good afternoon" if hour < 18 else "Good evening"

    return render(request, "items/dashboard.html", {
        "greeting": greeting,
        "expiring": expiring[:10],
        "expiring_count": expiring.count(),
        "open_count": open_items.count(),
        "listed_count": open_items.filter(status=ItemStatus.LISTED).count(),
        "summary": summary,
        "year": year,
        "seller_queue": seller_queue,
        "recent_notifications": user.notifications.all()[:5],
        "shop_listings": Listing.objects.live().filter(seller=user).select_related("item")[:5],
        "soon_days": soon,
    })


VIEWS = {
    "current": ("Current", Q(status__in=[ItemStatus.ACTIVE, ItemStatus.LISTED])),
    "listed": ("Listed", Q(status=ItemStatus.LISTED)),
    "history": ("History", Q(status__in=[ItemStatus.USED, ItemStatus.SOLD, ItemStatus.EXPIRED])),
}


@login_required
def item_list(request):
    view = request.GET.get("view", "current")
    if view not in VIEWS:
        view = "current"
    # "Bought" badge: worked out in the same query instead of one extra query per card.
    items = (request.user.items.filter(VIEWS[view][1]).select_related("category")
             .annotate(was_bought_flag=Exists(Order.objects.filter(buyer_item=OuterRef("pk")))))

    q = request.GET.get("q", "").strip()
    if q:
        items = items.filter(
            Q(item_name__icontains=q) | Q(provider__icontains=q)
            | Q(reference_number__icontains=q) | Q(description__icontains=q)
        )
    category_id = request.GET.get("category")
    if category_id and category_id.isdigit():
        items = items.filter(category_id=category_id)
    if view == "history":
        items = items.order_by("-updated_at")

    return render(request, "items/item_list.html", {
        "items": items,
        "view": view,
        "views": [(k, v[0]) for k, v in VIEWS.items()],
        "categories": Category.objects.all(),
        "q": q,
        "category_id": category_id,
    })


@login_required
def item_create(request):
    form = ItemForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        item = form.save(commit=False)
        item.user = request.user
        item.save()
        schedule_reminders(item)
        request.session["celebrate"] = {
            "title": "Item added",
            "text": f"{item.item_name} · we'll remind you before it expires.",
        }
        return redirect(item)
    return render(request, "items/item_form.html", {"form": form, "is_new": True})


@login_required
def item_update(request, pk):
    item = get_object_or_404(Item, pk=pk, user=request.user)
    if not item.is_open:
        messages.error(request, "This item is closed and can't be edited.")
        return redirect(item)
    form = ItemForm(request.POST or None, request.FILES or None, instance=item)
    if request.method == "POST" and form.is_valid():
        changed = "expiry_date" in form.changed_data
        item = form.save()
        if changed:
            schedule_reminders(item)
        messages.success(request, "Changes saved.")
        return redirect(item)
    return render(request, "items/item_form.html", {"form": form, "item": item, "is_new": False})


@login_required
def item_delete(request, pk):
    item = get_object_or_404(Item, pk=pk, user=request.user)
    if item.listings.filter(orders__isnull=False).exists():
        messages.error(request, "This item has shop orders, so it can't be deleted.")
        return redirect(item)
    if request.method == "POST":
        name = item.item_name
        item.delete()
        messages.success(request, f"Deleted {name}.")
        return redirect("items:list")
    return render(request, "items/item_confirm_delete.html", {"item": item})


@login_required
def item_detail(request, pk):
    item = get_object_or_404(Item.objects.select_related("category"), pk=pk, user=request.user)
    return render(request, "items/item_detail.html", {
        "item": item,
        "reminders": item.reminders.all(),
        "reminder_form": ReminderForm(item=item),
        "listings": item.listings.all().order_by("-created_at"),
        "records": item.impact_records.all(),
        "used_form": MarkUsedForm(initial={"amount_value": item.price or None}),
    })


@login_required
@require_POST
def item_mark_used(request, pk):
    item = get_object_or_404(Item, pk=pk, user=request.user)
    if item.status != ItemStatus.ACTIVE:
        messages.error(request, "Only active items that aren't listed can be marked as used.")
        return redirect(item)
    form = MarkUsedForm(request.POST)
    if form.is_valid():
        item.status = ItemStatus.USED
        item.save(update_fields=["status", "updated_at"])
        item.reminders.filter(is_sent=False).delete()
        record_outcome(item, OutcomeStatus.SAVED, amount=form.cleaned_data["amount_value"] or 0,
                       notes="Used before it expired.")
        messages.success(request, f"Nice — {item.item_name} was used in time.")
    return redirect(item)


@login_required
def item_suggest(request):
    """Live search suggestions for the top search bar (JSON).

    Matches the signed-in user's own items by name, shop, batch number or
    category. Items still in hand come first, soonest expiry first.
    """
    from .templatetags.shelf import money, photo_url

    q = request.GET.get("q", "").strip()
    if len(q) < 1:
        return JsonResponse({"query": q, "results": [], "total": 0})
    matches = request.user.items.filter(
        Q(item_name__icontains=q) | Q(provider__icontains=q)
        | Q(reference_number__icontains=q) | Q(category__category_name__icontains=q)
    ).select_related("category")
    total = matches.count()
    matches = matches.annotate(
        closed=Case(
            When(status__in=[ItemStatus.ACTIVE, ItemStatus.LISTED], then=Value(0)),
            default=Value(1), output_field=IntegerField(),
        ),
        starts=Case(When(item_name__istartswith=q, then=Value(0)), default=Value(1), output_field=IntegerField()),
    ).order_by("closed", "starts", "expiry_date")[:6]
    results = [
        {
            "name": it.item_name,
            "url": it.get_absolute_url(),
            "price": money(it.price) if it.price else "",
            "image": photo_url(it.image),
            "initial": (it.item_name[:1] or "?").upper(),
            "category": str(it.category or ""),
            "when": it.days_left_label,
            "tone": it.freshness,
            "status": it.get_status_display() if it.status != ItemStatus.ACTIVE else "",
        }
        for it in matches
    ]
    return JsonResponse({"query": q, "results": results, "total": total})


def qr_payload(item):
    """What an ExpiryBox QR label contains: the item's details as compact JSON."""
    import json

    data = {
        "app": "expirybox",
        "name": item.item_name,
        "expiry": item.expiry_date.isoformat(),
        "price": float(item.price or 0),
        "category": item.category.category_name if item.category else "",
        "provider": item.provider,
        "batch": item.reference_number,
        "purchase": item.purchase_date.isoformat() if item.purchase_date else "",
    }
    return json.dumps({k: v for k, v in data.items() if v not in ("", None)}, ensure_ascii=False, separators=(",", ":"))


@login_required
def item_qr(request, pk):
    """SVG QR label for an item. Scanning it on 'Add item' fills in the same details."""
    import segno
    from django.http import HttpResponse

    item = get_object_or_404(Item, pk=pk, user=request.user)
    qr = segno.make(qr_payload(item), error="m", micro=False)
    svg = qr.svg_inline(scale=8, border=2, dark="#1e2330", light="#ffffff")
    response = HttpResponse(svg, content_type="image/svg+xml")
    if request.GET.get("download"):
        safe = "".join(ch if ch.isalnum() else "-" for ch in item.item_name)[:40].strip("-") or "item"
        response["Content-Disposition"] = f'attachment; filename="expirybox-{safe}.svg"'
    return response
