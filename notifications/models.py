from django.conf import settings
from django.db import models


class Reminder(models.Model):
    """
    App3_Notifications.Reminder
    pk, item, reminderDate, reminderType, isSent, createdAt
    A reminder belongs to an Item; when its date arrives it produces a Notification.
    """

    class Type(models.TextChoices):
        WEEK_BEFORE = "WEEK_BEFORE", "1 week before"
        THREE_DAYS = "THREE_DAYS", "3 days before"
        DAY_BEFORE = "DAY_BEFORE", "1 day before"
        ON_EXPIRY = "ON_EXPIRY", "On expiry day"
        CUSTOM = "CUSTOM", "Custom"

    item = models.ForeignKey("items.Item", on_delete=models.CASCADE, related_name="reminders")
    reminder_date = models.DateField()
    reminder_type = models.CharField(max_length=12, choices=Type.choices, default=Type.CUSTOM)
    is_sent = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["reminder_date"]

    def __str__(self):
        return f"{self.item} · {self.get_reminder_type_display()} ({self.reminder_date})"


class Notification(models.Model):
    """
    App3_Notifications.Notification
    pk, user, item, order, message, notificationType, isRead, createdAt
    """

    class Type(models.TextChoices):
        EXPIRY = "EXPIRY", "Expiry reminder"
        EXPIRED = "EXPIRED", "Item expired"
        ORDER = "ORDER", "Order update"
        PAYMENT = "PAYMENT", "Payment"
        REVIEW = "REVIEW", "Review"
        SYSTEM = "SYSTEM", "System"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications"
    )
    item = models.ForeignKey(
        "items.Item", on_delete=models.CASCADE, null=True, blank=True, related_name="notifications"
    )
    order = models.ForeignKey(
        "marketplace.Order", on_delete=models.CASCADE, null=True, blank=True, related_name="notifications"
    )
    message = models.CharField(max_length=255)
    notification_type = models.CharField(max_length=10, choices=Type.choices, default=Type.SYSTEM)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.message

    @property
    def target_url(self):
        if self.order_id:
            return self.order.get_absolute_url()
        if self.item_id:
            return self.item.get_absolute_url()
        return None
