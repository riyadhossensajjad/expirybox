"""Order lifecycle: place → pay → complete, with cancel and refund paths."""
import uuid

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from impact.models import OutcomeStatus
from impact.services import record_outcome
from items.models import Item, ItemStatus
from notifications.models import Notification
from notifications.services import notify, schedule_reminders

from .models import Listing, ListingStatus, Order, OrderStatus, Payment

OPEN_ORDER_STATUSES = [OrderStatus.PENDING, OrderStatus.PAID]


def _release_stock(order):
    """Give an order's quantity back to its listing and re-open it if needed."""
    listing = Listing.objects.select_for_update().get(pk=order.listing_id)
    listing.quantity += order.quantity
    if listing.status == ListingStatus.SOLD:
        listing.status = ListingStatus.ACTIVE
        if listing.item.status == ItemStatus.SOLD:
            listing.item.status = ItemStatus.LISTED
            listing.item.save(update_fields=["status", "updated_at"])
    listing.save(update_fields=["quantity", "status"])


def _add_to_buyer_items(order):
    """Put a copy of the bought item into the buyer's own list, with reminders."""
    src = order.listing.item
    seller = order.listing.seller
    qty = f"{order.quantity} × " if order.quantity > 1 else ""
    note = f"Bought in the shop from {seller.name} (order #{order.pk})."
    item = Item.objects.create(
        user=order.buyer,
        category=src.category,
        item_name=f"{qty}{src.item_name}"[:150],
        description=f"{note}\n\n{src.description}".strip(),
        provider=src.provider or seller.name,
        purchase_date=timezone.localdate(),
        expiry_date=src.expiry_date,
        reference_number=src.reference_number,
        price=order.total_price,
        image=src.image.name if src.image else "",
    )
    schedule_reminders(item)
    order.buyer_item = item
    order.save(update_fields=["buyer_item"])
    return item


@transaction.atomic
def place_order(listing_id, buyer, quantity, delivery_method):
    listing = Listing.objects.select_for_update().select_related("item", "seller").get(pk=listing_id)
    if listing.seller_id == buyer.pk:
        raise ValidationError("You can't buy your own listing.")
    if not listing.is_buyable:
        raise ValidationError("This listing is no longer available.")
    if quantity < 1 or quantity > listing.quantity:
        raise ValidationError(f"Choose a quantity between 1 and {listing.quantity}.")

    order = Order.objects.create(
        listing=listing,
        buyer=buyer,
        quantity=quantity,
        total_price=listing.sale_price * quantity,
        delivery_method=delivery_method,
    )
    # Reserve the stock straight away so two buyers can't take the last unit.
    listing.quantity -= quantity
    if listing.quantity == 0:
        listing.status = ListingStatus.SOLD
        listing.item.status = ItemStatus.SOLD
        listing.item.save(update_fields=["status", "updated_at"])
    listing.save(update_fields=["quantity", "status"])

    notify(
        listing.seller,
        f"{buyer.name} ordered {quantity} × {listing.item.item_name}. Waiting for payment.",
        Notification.Type.ORDER,
        order=order,
    )
    return order


@transaction.atomic
def pay_order(order, method):
    order = Order.objects.select_for_update().get(pk=order.pk)
    if order.status != OrderStatus.PENDING:
        raise ValidationError("Only orders awaiting payment can be paid.")
    payment = Payment.objects.create(
        order=order,
        amount=order.total_price,
        method=method,
        transaction_ref=f"SL-{uuid.uuid4().hex[:10].upper()}",
    )
    order.status = OrderStatus.PAID
    order.save(update_fields=["status"])
    notify(
        order.listing.seller,
        f"Payment received for order #{order.pk} ({order.listing.item.item_name}). "
        f"Hand it over, then mark it as handed over.",
        Notification.Type.PAYMENT,
        order=order,
    )
    notify(
        order.buyer,
        f"Payment confirmed for order #{order.pk}. It will be added to your items once you "
        f"pick it up or the seller delivers it.",
        Notification.Type.PAYMENT,
        order=order,
    )
    return payment


@transaction.atomic
def complete_order(order, by_user=None):
    """Mark a paid order as handed over (picked up or delivered).

    Either side can do this: the seller after delivering, or the buyer after
    picking it up. Only now does the item move into the buyer's own list.
    """
    order = Order.objects.select_for_update().select_related("listing__item", "listing__seller", "buyer").get(pk=order.pk)
    if order.status != OrderStatus.PAID:
        raise ValidationError("Only paid orders can be marked as handed over.")
    order.status = OrderStatus.COMPLETED
    order.completed_at = timezone.now()
    order.save(update_fields=["status", "completed_at"])
    record_outcome(
        order.listing.item,
        OutcomeStatus.SOLD,
        amount=order.total_price,
        order=order,
        notes=f"Sold {order.quantity} to {order.buyer.name}.",
    )
    bought = _add_to_buyer_items(order)
    by_buyer = by_user is not None and by_user.pk == order.buyer_id
    notify(
        order.buyer,
        f"{bought.item_name} is now in your items and we'll remind you before it expires. "
        f"How was it? Leave {order.listing.seller.name} a review.",
        Notification.Type.ORDER,
        order=order,
        item=bought,
    )
    if by_buyer:
        notify(
            order.listing.seller,
            f"{order.buyer.name} confirmed they received order #{order.pk}. The sale is added to your impact.",
            Notification.Type.ORDER,
            order=order,
        )
    return order


@transaction.atomic
def cancel_order(order, by_user):
    order = Order.objects.select_for_update().get(pk=order.pk)
    if order.status != OrderStatus.PENDING:
        raise ValidationError("Only orders awaiting payment can be cancelled.")
    order.status = OrderStatus.CANCELLED
    order.save(update_fields=["status"])
    _release_stock(order)
    other = order.listing.seller if by_user.pk == order.buyer_id else order.buyer
    notify(other, f"Order #{order.pk} was cancelled by {by_user.name}.", Notification.Type.ORDER, order=order)
    return order


@transaction.atomic
def refund_order(order):
    order = Order.objects.select_for_update().get(pk=order.pk)
    if order.status != OrderStatus.PAID:
        raise ValidationError("Only paid orders can be refunded.")
    order.status = OrderStatus.REFUNDED
    order.save(update_fields=["status"])
    Payment.objects.filter(order=order).update(status=Payment.Status.REFUNDED)
    _release_stock(order)
    notify(
        order.buyer,
        f"Order #{order.pk} was refunded by the seller.",
        Notification.Type.PAYMENT,
        order=order,
    )
    return order


@transaction.atomic
def cancel_listing(listing):
    if listing.orders.filter(status__in=OPEN_ORDER_STATUSES).exists():
        raise ValidationError("Finish or cancel the open orders on this listing first.")
    listing.status = ListingStatus.CANCELLED
    listing.save(update_fields=["status"])
    item = listing.item
    if item.status == ItemStatus.LISTED:
        item.status = ItemStatus.ACTIVE
        item.save(update_fields=["status", "updated_at"])
    return listing
