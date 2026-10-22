from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.urls import reverse
from django.utils import timezone


class ListingStatus(models.TextChoices):
    DRAFT = "DRAFT", "Draft"
    ACTIVE = "ACTIVE", "Active"
    SOLD = "SOLD", "Sold"
    EXPIRED = "EXPIRED", "Expired"
    CANCELLED = "CANCELLED", "Cancelled"


class OrderStatus(models.TextChoices):
    PENDING = "PENDING", "Awaiting payment"
    PAID = "PAID", "Paid"
    COMPLETED = "COMPLETED", "Completed"
    CANCELLED = "CANCELLED", "Cancelled"
    REFUNDED = "REFUNDED", "Refunded"


class ListingQuerySet(models.QuerySet):
    def live(self):
        return self.filter(
            status=ListingStatus.ACTIVE,
            quantity__gt=0,
            available_until__gte=timezone.localdate(),
        )


class Listing(models.Model):
    """
    App5_Marketplace.Listing
    pk, item, seller, originalPrice, salePrice, quantity, pickupLocation,
    availableUntil, status, createdAt
    """

    item = models.ForeignKey("items.Item", on_delete=models.CASCADE, related_name="listings")
    seller = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="listings"
    )
    original_price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    sale_price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    quantity = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
    pickup_location = models.CharField(max_length=200)
    available_until = models.DateField()
    status = models.CharField(max_length=10, choices=ListingStatus.choices, default=ListingStatus.ACTIVE)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = ListingQuerySet.as_manager()

    class Meta:
        ordering = ["available_until", "-created_at"]

    def __str__(self):
        return f"{self.item} · {self.sale_price}"

    def get_absolute_url(self):
        return reverse("marketplace:listing_detail", args=[self.pk])

    @property
    def discount_pct(self):
        if not self.original_price:
            return 0
        return max(0, round((1 - self.sale_price / self.original_price) * 100))

    @property
    def is_buyable(self):
        return (
            self.status == ListingStatus.ACTIVE
            and self.quantity > 0
            and self.available_until >= timezone.localdate()
        )


class Order(models.Model):
    """
    App5_Marketplace.Order
    pk, listing, buyer, quantity, totalPrice, deliveryMethod, status,
    createdAt, completedAt
    """

    class Delivery(models.TextChoices):
        PICKUP = "PICKUP", "Pick up from seller"
        DELIVERY = "DELIVERY", "Seller delivers"

    listing = models.ForeignKey(Listing, on_delete=models.CASCADE, related_name="orders")
    buyer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="orders")
    quantity = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
    total_price = models.DecimalField(max_digits=10, decimal_places=2)
    delivery_method = models.CharField(max_length=10, choices=Delivery.choices, default=Delivery.PICKUP)
    status = models.CharField(max_length=10, choices=OrderStatus.choices, default=OrderStatus.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    # The copy of the item that lands in the buyer's own list once they pay.
    buyer_item = models.ForeignKey(
        "items.Item", on_delete=models.SET_NULL, null=True, blank=True, related_name="bought_via"
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Order #{self.pk} · {self.listing.item}"

    def get_absolute_url(self):
        return reverse("marketplace:order_detail", args=[self.pk])

    @property
    def seller(self):
        return self.listing.seller

    @property
    def is_reviewable(self):
        return self.status == OrderStatus.COMPLETED and not hasattr(self, "review")


class Payment(models.Model):
    """
    App5_Marketplace.Payment — 0..1 per Order
    pk, order, amount, method, transactionRef, status, paidAt
    """

    class Method(models.TextChoices):
        CARD = "CARD", "Card"
        BKASH = "BKASH", "bKash"
        NAGAD = "NAGAD", "Nagad"
        CASH = "CASH", "Cash on pickup"

    class Status(models.TextChoices):
        SUCCESS = "SUCCESS", "Successful"
        REFUNDED = "REFUNDED", "Refunded"

    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name="payment")
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    method = models.CharField(max_length=6, choices=Method.choices)
    transaction_ref = models.CharField(max_length=40, unique=True)
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.SUCCESS)
    paid_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.transaction_ref} · {self.amount}"


class Review(models.Model):
    """
    App5_Marketplace.Review — 0..1 per Order
    pk, order, reviewer, seller, rating, comment, createdAt
    """

    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name="review")
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reviews_written"
    )
    seller = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reviews_received"
    )
    rating = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.rating}★ for {self.seller} by {self.reviewer}"
