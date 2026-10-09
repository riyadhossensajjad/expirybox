from django.contrib import admin

from .models import ImpactRecord, ImpactSummary


@admin.register(ImpactRecord)
class ImpactRecordAdmin(admin.ModelAdmin):
    list_display = ["item", "outcome", "amount_value", "resolved_date"]
    list_filter = ["outcome"]


@admin.register(ImpactSummary)
class ImpactSummaryAdmin(admin.ModelAdmin):
    list_display = ["user", "year", "total_saved", "total_lost", "total_earned"]
