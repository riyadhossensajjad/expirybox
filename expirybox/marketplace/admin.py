from django.contrib import admin

from .models import Listing, Order, Payment, Review


@admin.register(Listing)
class ListingAdmin(admin.ModelAdmin):
    list_display = ["item", "seller", "sale_price", "quantity", "available_until", "status"]
    list_filter = ["status"]


class PaymentInline(admin.StackedInline):
    model = Payment
    extra = 0


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ["id", "listing", "buyer", "quantity", "total_price", "status", "created_at"]
    list_filter = ["status", "delivery_method"]
    inlines = [PaymentInline]


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ["transaction_ref", "order", "amount", "method", "status", "paid_at"]


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ["seller", "reviewer", "rating", "created_at"]
