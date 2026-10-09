from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from items.models import Category, Item, ItemStatus

from . import services
from .forms import ListingForm, OrderForm, PaymentForm, ReviewForm
from .models import Listing, ListingStatus, Order, OrderStatus, Review

SORTS = {
    "soonest": ("Expiring soonest", ["item__expiry_date", "-created_at"]),
    "cheapest": ("Lowest price", ["sale_price"]),
    "discount": ("Biggest discount", None),
    "newest": ("Newest", ["-created_at"]),
}


def _error_text(exc):
    return " ".join(exc.messages)


def browse(request):
    listings = Listing.objects.live().select_related("item", "item__category", "seller")
    if request.user.is_authenticated and request.GET.get("mine") != "1":
        listings = listings.exclude(seller=request.user)

    q = request.GET.get("q", "").strip()
    if q:
        listings = listings.filter(
            Q(item__item_name__icontains=q) | Q(item__description__icontains=q)
            | Q(item__provider__icontains=q) | Q(pickup_location__icontains=q)
        )
    category_id = request.GET.get("category")
    if category_id and category_id.isdigit():
        listings = listings.filter(item__category_id=category_id)

    sort = request.GET.get("sort", "soonest")
    if sort not in SORTS:
        sort = "soonest"
    order_by = SORTS[sort][1]
    if order_by:
        listings = listings.order_by(*order_by)
    else:
        listings = sorted(listings, key=lambda l: -l.discount_pct)

    return render(request, "marketplace/browse.html", {
        "listings": listings,
        "categories": Category.objects.all(),
        "q": q,
        "category_id": category_id,
        "sort": sort,
        "sorts": [(k, v[0]) for k, v in SORTS.items()],
    })


def listing_detail(request, pk):
    listing = get_object_or_404(Listing.objects.select_related("item", "item__category", "seller"), pk=pk)
    is_owner = request.user.is_authenticated and listing.seller_id == request.user.pk
    if listing.status == ListingStatus.DRAFT and not is_owner:
        return redirect("marketplace:browse")

    form = OrderForm(request.POST or None, listing=listing, initial={"quantity": 1})
    if request.method == "POST":
        if not request.user.is_authenticated:
            return redirect_to_login(listing.get_absolute_url())
        if form.is_valid():
            try:
                order = services.place_order(
                    listing.pk, request.user,
                    form.cleaned_data["quantity"], form.cleaned_data["delivery_method"],
                )
            except ValidationError as exc:
                messages.error(request, _error_text(exc))
                return redirect(listing)
            messages.success(request, "Order placed. Pay now to confirm it with the seller.")
            return redirect("marketplace:order_pay", pk=order.pk)

    return render(request, "marketplace/listing_detail.html", {
        "listing": listing,
        "form": form,
        "is_owner": is_owner,
        "seller_reviews": listing.seller.reviews_received.select_related("reviewer")[:3],
        "orders": listing.orders.select_related("buyer") if is_owner else None,
    })


@login_required
def listing_create(request, item_pk):
    item = get_object_or_404(Item, pk=item_pk, user=request.user)
    if not item.can_be_listed:
        messages.error(request, "Only active, unexpired items that aren't already listed can be sold.")
        return redirect(item)

    form = ListingForm(
        request.POST or None, item=item,
        initial={
            "available_until": item.expiry_date, "pickup_location": request.user.address, "quantity": 1,
            "original_price": item.price or None,
        },
    )
    if request.method == "POST" and form.is_valid():
        listing = form.save(commit=False)
        listing.item = item
        listing.seller = request.user
        draft = "save_draft" in request.POST
        listing.status = ListingStatus.DRAFT if draft else ListingStatus.ACTIVE
        listing.save()
        if not draft:
            item.status = ItemStatus.LISTED
            item.save(update_fields=["status", "updated_at"])
            messages.success(request, f"{item.item_name} is live in the shop.")
        else:
            messages.success(request, "Draft saved. Publish it when you're ready.")
        return redirect(listing)
    return render(request, "marketplace/listing_form.html", {"form": form, "item": item, "is_new": True})


@login_required
def listing_edit(request, pk):
    listing = get_object_or_404(Listing, pk=pk, seller=request.user)
    if listing.status not in (ListingStatus.ACTIVE, ListingStatus.DRAFT):
        messages.error(request, "Closed listings can't be edited.")
        return redirect(listing)
    form = ListingForm(request.POST or None, instance=listing, item=listing.item)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Listing updated.")
        return redirect(listing)
    return render(request, "marketplace/listing_form.html", {
        "form": form, "item": listing.item, "listing": listing, "is_new": False,
    })


@login_required
@require_POST
def listing_publish(request, pk):
    listing = get_object_or_404(Listing, pk=pk, seller=request.user, status=ListingStatus.DRAFT)
    if not listing.item.can_be_listed:
        messages.error(request, "This item can no longer be listed.")
        return redirect(listing)
    listing.status = ListingStatus.ACTIVE
    listing.save(update_fields=["status"])
    listing.item.status = ItemStatus.LISTED
    listing.item.save(update_fields=["status", "updated_at"])
    messages.success(request, "Listing published.")
    return redirect(listing)


@login_required
@require_POST
def listing_cancel(request, pk):
    listing = get_object_or_404(Listing, pk=pk, seller=request.user)
    try:
        services.cancel_listing(listing)
        messages.success(request, "Listing taken down. The item is back in your active list.")
    except ValidationError as exc:
        messages.error(request, _error_text(exc))
    return redirect(listing)


@login_required
def selling(request):
    listings = request.user.listings.select_related("item").order_by("-created_at")
    sales = Order.objects.filter(listing__seller=request.user).select_related("listing__item", "buyer")
    return render(request, "marketplace/selling.html", {"listings": listings, "sales": sales})


@login_required
def buying(request):
    orders = request.user.orders.select_related("listing__item", "listing__seller")
    return render(request, "marketplace/buying.html", {"orders": orders})


def _get_order_for(user, pk):
    order = get_object_or_404(
        Order.objects.select_related("listing__item", "listing__seller", "buyer"), pk=pk
    )
    if user.pk not in (order.buyer_id, order.listing.seller_id):
        from django.http import Http404
        raise Http404
    return order


@login_required
def order_detail(request, pk):
    order = _get_order_for(request.user, pk)
    is_buyer = order.buyer_id == request.user.pk
    review_form = ReviewForm() if is_buyer and order.is_reviewable else None
    return render(request, "marketplace/order_detail.html", {
        "order": order,
        "is_buyer": is_buyer,
        "payment": getattr(order, "payment", None),
        "review": getattr(order, "review", None),
        "review_form": review_form,
    })


@login_required
def order_pay(request, pk):
    order = _get_order_for(request.user, pk)
    if order.buyer_id != request.user.pk or order.status != OrderStatus.PENDING:
        return redirect(order)
    form = PaymentForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            payment = services.pay_order(order, form.cleaned_data["method"])
            messages.success(request, f"Paid {payment.amount}. The seller has been notified.")
        except ValidationError as exc:
            messages.error(request, _error_text(exc))
        return redirect(order)
    return render(request, "marketplace/order_pay.html", {"order": order, "form": form})


@login_required
@require_POST
def order_action(request, pk, action):
    order = _get_order_for(request.user, pk)
    is_seller = order.listing.seller_id == request.user.pk
    try:
        if action == "complete":
            services.complete_order(order, by_user=request.user)
            if is_seller:
                messages.success(request, "Marked as handed over. The sale was added to your impact.")
            else:
                messages.success(request, "Marked as received. It's now in your items with expiry reminders.")
        elif action == "refund" and is_seller:
            services.refund_order(order)
            messages.success(request, "Order refunded and stock returned to the listing.")
        elif action == "cancel":
            services.cancel_order(order, request.user)
            messages.success(request, "Order cancelled.")
        else:
            messages.error(request, "That action isn't available.")
    except ValidationError as exc:
        messages.error(request, _error_text(exc))
    return redirect(order)


@login_required
@require_POST
def review_create(request, pk):
    order = _get_order_for(request.user, pk)
    if order.buyer_id != request.user.pk or not order.is_reviewable:
        messages.error(request, "You can review an order once it's completed, and only once.")
        return redirect(order)
    form = ReviewForm(request.POST)
    if form.is_valid():
        review = form.save(commit=False)
        review.order = order
        review.reviewer = request.user
        review.seller = order.listing.seller
        review.save()
        from notifications.models import Notification
        from notifications.services import notify
        notify(review.seller, f"{request.user.name} left you a {review.rating}★ review.",
               Notification.Type.REVIEW, order=order)
        messages.success(request, "Thanks — your review is posted.")
    else:
        messages.error(request, "Choose a star rating.")
    return redirect(order)
