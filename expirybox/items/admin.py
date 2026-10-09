from django.contrib import admin

from .models import Category, Item


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ["category_name", "description"]
    search_fields = ["category_name"]


@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    list_display = ["item_name", "user", "category", "expiry_date", "status"]
    list_filter = ["status", "category"]
    search_fields = ["item_name", "provider", "reference_number"]
    date_hierarchy = "expiry_date"
