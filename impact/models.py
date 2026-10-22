from django.conf import settings
from django.db import models


class OutcomeStatus(models.TextChoices):
    SAVED = "SAVED", "Saved (used in time)"
    SOLD = "SOLD", "Sold in the shop"
    LOST = "LOST", "Lost (expired)"


class ImpactRecord(models.Model):
    """
    App4_Impact.ImpactRecord
    pk, item, order, outcome, amountValue, resolvedDate, notes, createdAt
    One record per item outcome: used it, sold it, or let it expire.
    """

    item = models.ForeignKey("items.Item", on_delete=models.CASCADE, related_name="impact_records")
    order = models.ForeignKey(
        "marketplace.Order", on_delete=models.SET_NULL, null=True, blank=True, related_name="impact_records"
    )
    outcome = models.CharField(max_length=5, choices=OutcomeStatus.choices)
    amount_value = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    resolved_date = models.DateField()
    notes = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-resolved_date", "-created_at"]

    def __str__(self):
        return f"{self.item} · {self.get_outcome_display()}"


class ImpactSummary(models.Model):
    """
    App4_Impact.ImpactSummary
    pk, user, year, totalSaved, totalLost, totalEarned
    Aggregates a user's ImpactRecords for one year.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="impact_summaries"
    )
    year = models.PositiveIntegerField()
    total_saved = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_lost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_earned = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    class Meta:
        ordering = ["-year"]
        unique_together = [("user", "year")]
        verbose_name_plural = "impact summaries"

    def __str__(self):
        return f"{self.user} · {self.year}"

    @property
    def total_kept(self):
        return self.total_saved + self.total_earned

    @property
    def rescue_rate(self):
        """Share of tracked value that was used or sold rather than lost."""
        whole = self.total_kept + self.total_lost
        return round(self.total_kept / whole * 100) if whole else None
