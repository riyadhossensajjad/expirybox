from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .forms import ImpactRecordForm
from .models import ImpactRecord, ImpactSummary, OutcomeStatus
from .services import recompute_summary


def _year_from(request):
    this_year = timezone.localdate().year
    try:
        return int(request.GET.get("year", this_year))
    except ValueError:
        return this_year


def build_sections(summary, records):
    """The three impact sections, in the order people think about them."""
    meta = [
        (OutcomeStatus.SOLD, "Earned from the shop", "sold", "tag",
         "Money you made selling items before they expired.", "item sold", "items sold",
         "Nothing sold yet. List an item that's expiring soon."),
        (OutcomeStatus.LOST, "Lost in expiration", "lost", "alert",
         "Value of items that expired before they were used or sold.", "item expired", "items expired",
         "Nothing has expired. Keep it up."),
        (OutcomeStatus.SAVED, "Saved by using", "saved", "check",
         "Value of items you used up before their date.", "item used", "items used",
         "Mark items as used to count what you saved."),
    ]
    totals = {
        OutcomeStatus.SOLD: summary.total_earned if summary else 0,
        OutcomeStatus.LOST: summary.total_lost if summary else 0,
        OutcomeStatus.SAVED: summary.total_saved if summary else 0,
    }
    grand = sum(totals.values()) or 0
    sections = []
    for outcome, title, kind, icon, blurb, one, many, empty in meta:
        recs = [r for r in records if r.outcome == outcome]
        total = totals[outcome]
        sections.append({
            "outcome": outcome, "title": title, "kind": kind, "icon": icon, "blurb": blurb,
            "total": total, "count": len(recs), "noun": one if len(recs) == 1 else many,
            "share": round(total / grand * 100) if grand else 0,
            "records": recs[:4], "more": max(len(recs) - 4, 0), "empty": empty,
        })
    return sections


def _year_data(user, year):
    summary = ImpactSummary.objects.filter(user=user, year=year).first()
    records = list(
        ImpactRecord.objects.filter(item__user=user, resolved_date__year=year)
        .select_related("item", "order").order_by("resolved_date", "created_at")
    )
    return summary, records


@login_required
def overview(request):
    this_year = timezone.localdate().year
    year = _year_from(request)
    summary, records = _year_data(request.user, year)
    years = sorted(
        set(request.user.impact_summaries.values_list("year", flat=True)) | {this_year}, reverse=True
    )
    recent_first = sorted(records, key=lambda r: (r.resolved_date, r.created_at), reverse=True)
    return render(request, "impact/overview.html", {
        "summary": summary,
        "records": recent_first,
        "year": year,
        "years": years,
        "sections": build_sections(summary, recent_first),
        "total_items": len(records),
    })


@login_required
def export_pdf(request):
    from .pdf import build_impact_pdf

    year = _year_from(request)
    summary, records = _year_data(request.user, year)
    sections = build_sections(summary, records)
    pdf = build_impact_pdf(request.user, year, summary, sections, records)
    response = HttpResponse(pdf, content_type="application/pdf")
    filename = f"expirybox-impact-{year}.pdf"
    disposition = "inline" if request.GET.get("view") == "1" else "attachment"
    response["Content-Disposition"] = f'{disposition}; filename="{filename}"'
    return response


@login_required
def record_edit(request, pk):
    record = get_object_or_404(ImpactRecord, pk=pk, item__user=request.user)
    form = ImpactRecordForm(request.POST or None, instance=record)
    if request.method == "POST" and form.is_valid():
        form.save()
        recompute_summary(request.user, record.resolved_date.year)
        messages.success(request, "Impact record updated.")
        return redirect(f"/impact/?year={record.resolved_date.year}")
    return render(request, "impact/record_form.html", {"form": form, "record": record})
