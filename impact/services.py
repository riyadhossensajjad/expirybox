"""Impact bookkeeping: one ImpactRecord per outcome, rolled up into ImpactSummary."""
from decimal import Decimal

from django.db.models import Sum
from django.utils import timezone

from .models import ImpactRecord, ImpactSummary, OutcomeStatus


def recompute_summary(user, year):
    records = ImpactRecord.objects.filter(item__user=user, resolved_date__year=year)
    totals = {
        row["outcome"]: row["total"] or Decimal("0")
        for row in records.values("outcome").annotate(total=Sum("amount_value"))
    }
    summary, _ = ImpactSummary.objects.get_or_create(user=user, year=year)
    summary.total_saved = totals.get(OutcomeStatus.SAVED, 0)
    summary.total_lost = totals.get(OutcomeStatus.LOST, 0)
    summary.total_earned = totals.get(OutcomeStatus.SOLD, 0)
    summary.save()
    return summary


def record_outcome(item, outcome, amount=0, order=None, notes="", resolved_date=None):
    record = ImpactRecord.objects.create(
        item=item,
        order=order,
        outcome=outcome,
        amount_value=amount or 0,
        resolved_date=resolved_date or timezone.localdate(),
        notes=notes,
    )
    recompute_summary(item.user, record.resolved_date.year)
    return record
