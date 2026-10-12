from django.contrib import admin

from .models import Notification, Reminder


@admin.register(Reminder)
class ReminderAdmin(admin.ModelAdmin):
    list_display = ["item", "reminder_date", "reminder_type", "is_sent"]
    list_filter = ["is_sent", "reminder_type"]


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ["user", "message", "notification_type", "is_read", "created_at"]
    list_filter = ["notification_type", "is_read"]
