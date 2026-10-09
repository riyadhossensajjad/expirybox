from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone


class Category(models.Model):
    """App2_Items.Category — pk, categoryName, description."""

    category_name = models.CharField(max_length=80, unique=True)
    description = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["category_name"]
        verbose_name_plural = "categories"

    def __str__(self):
        return self.category_name


class ItemStatus(models.TextChoices):
    ACTIVE = "ACTIVE", "Active"
    LISTED = "LISTED", "Listed for sale"
    SOLD = "SOLD", "Sold"
    USED = "USED", "Used"
    EXPIRED = "EXPIRED", "Expired"


class ItemQuerySet(models.QuerySet):
    def open(self):
        """Items still in the user's possession and not yet expired."""
        return self.filter(status__in=[ItemStatus.ACTIVE, ItemStatus.LISTED])

    def expiring_within(self, days):
        today = timezone.localdate()
        return self.open().filter(expiry_date__lte=today + timezone.timedelta(days=days))


class Item(models.Model):
    """
    App2_Items.Item
    pk, user, category, itemName, description, provider, purchaseDate,
    expiryDate, referenceNumber, status, createdAt, updatedAt
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="items"
    )
    category = models.ForeignKey(
        Category, on_delete=models.SET_NULL, null=True, blank=True, related_name="items"
    )
    item_name = models.CharField("name", max_length=150)
    description = models.TextField(blank=True)
    provider = models.CharField(
        max_length=120, blank=True, help_text="Shop, brand or pharmacy you got it from."
    )
    purchase_date = models.DateField(null=True, blank=True)
    expiry_date = models.DateField()
    price = models.DecimalField(
        "value", max_digits=10, decimal_places=2, default=0,
        help_text="What it cost you. Used for listings and your impact totals.",
    )
    image = models.ImageField("photo", upload_to="items/", blank=True)
    reference_number = models.CharField(
        max_length=80, blank=True, help_text="Batch, lot or receipt number."
    )
    status = models.CharField(
        max_length=10, choices=ItemStatus.choices, default=ItemStatus.ACTIVE
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = ItemQuerySet.as_manager()

    class Meta:
        ordering = ["expiry_date", "item_name"]

    def __str__(self):
        return self.item_name

    def get_absolute_url(self):
        return reverse("items:detail", args=[self.pk])

    # --- Freshness helpers used by templates --------------------------------
    @property
    def days_left(self):
        return (self.expiry_date - timezone.localdate()).days

    @property
    def is_open(self):
        return self.status in (ItemStatus.ACTIVE, ItemStatus.LISTED)

    @property
    def freshness(self):
        """'fresh', 'soon', 'urgent' or 'gone' — drives colour in the UI."""
        if not self.is_open or self.days_left < 0:
            return "gone"
        if self.days_left <= 2:
            return "urgent"
        if self.days_left <= settings.EXPIRING_SOON_DAYS:
            return "soon"
        return "fresh"

    @property
    def freshness_pct(self):
        """How much of the item's life is left, 0–100, for the ring gauge."""
        if not self.is_open or self.days_left <= 0:
            return 0
        start = self.purchase_date or self.created_at.date()
        total = max((self.expiry_date - start).days, 1)
        return max(0, min(100, round(self.days_left / total * 100)))

    @property
    def days_left_label(self):
        d = self.days_left
        if self.status in (ItemStatus.SOLD, ItemStatus.USED):
            return self.get_status_display()
        if d < 0:
            return f"Expired {-d} day{'s' if d != -1 else ''} ago"
        if d == 0:
            return "Expires today"
        if d == 1:
            return "Expires tomorrow"
        return f"{d} days left"

    @property
    def can_be_listed(self):
        return self.status == ItemStatus.ACTIVE and self.days_left >= 0

    @property
    def was_bought(self):
        """True if this item came from a marketplace order (uses the list view's annotation when present)."""
        flag = getattr(self, "was_bought_flag", None)
        return self.bought_via.exists() if flag is None else flag

    @property
    def purchase_order(self):
        """The marketplace order this item came from, if the user bought it here."""
        return self.bought_via.select_related("listing__seller").first()

    @property
    def active_listing(self):
        return self.listings.filter(status__in=["ACTIVE", "DRAFT"]).first()
