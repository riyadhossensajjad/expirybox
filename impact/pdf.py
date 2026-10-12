"""Impact report as a downloadable PDF (ReportLab).

Layout (A4): dark header band, a "kept" summary with its ring, the three
metric cards (earned / lost / saved) each with a ring, a share bar, and a
table of every outcome for the year.
"""
from decimal import Decimal
from io import BytesIO
from pathlib import Path

from django.conf import settings
from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Flowable, KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)

from .models import OutcomeStatus

FONT_DIR = Path(__file__).resolve().parent / "fonts"
_fonts_ready = False


def _register_fonts():
    global _fonts_ready
    if _fonts_ready:
        return
    for name, file in [
        ("Inter", "Inter-Regular.ttf"), ("Inter-SemiBold", "Inter-SemiBold.ttf"),
        ("Inter-Bold", "Inter-Bold.ttf"), ("Inter-ExtraBold", "Inter-ExtraBold.ttf"),
        ("Taka", "Taka.ttf"),
    ]:
        pdfmetrics.registerFont(TTFont(name, str(FONT_DIR / file)))
    pdfmetrics.registerFontFamily("Inter", normal="Inter", bold="Inter-Bold", italic="Inter", boldItalic="Inter-Bold")
    _fonts_ready = True


# Palette (matches the website's light theme)
INK = colors.HexColor("#1e2330")
INK2 = colors.HexColor("#5d626e")
INK3 = colors.HexColor("#8c909a")
LINE = colors.HexColor("#e4e4df")
SURFACE2 = colors.HexColor("#f6f6f4")
LIME = colors.HexColor("#43e660")
BLUE = colors.HexColor("#2563eb")
RED = colors.HexColor("#e5484d")
GREEN = colors.HexColor("#16a34a")
AMBER = colors.HexColor("#fbbf24")
VIOLET = colors.HexColor("#8b3dff")
WHITE = colors.white

TONES = {OutcomeStatus.SOLD: BLUE, OutcomeStatus.LOST: RED, OutcomeStatus.SAVED: GREEN}
LABELS = {OutcomeStatus.SOLD: "Sold", OutcomeStatus.LOST: "Lost", OutcomeStatus.SAVED: "Saved"}


def _tint(c, amount):
    """Mix a colour with white (amount 0..1 of the colour kept)."""
    return colors.Color(1 - (1 - c.red) * amount, 1 - (1 - c.green) * amount, 1 - (1 - c.blue) * amount)


def _amount(value):
    value = Decimal(value or 0)
    return f"{value:,.0f}" if value == value.to_integral() else f"{value:,.2f}"


def _money_width(text, font, size):
    return pdfmetrics.stringWidth(settings.CURRENCY_SYMBOL, "Taka", size) + pdfmetrics.stringWidth(text, font, size)


def draw_money(c, x, y, value, font="Inter-Bold", size=12, color=INK, align="left"):
    """Draw "৳1,250": the Taka sign comes from its own font, the digits from Inter."""
    text = _amount(value)
    w = _money_width(text, font, size)
    if align == "right":
        x -= w
    elif align == "center":
        x -= w / 2
    # saveState/restoreState keeps the outline settings below from leaking into
    # text drawn later (PDF text render mode otherwise stays switched on).
    c.saveState()
    c.setFillColor(color)
    t = c.beginText(x, y)
    t.setFont("Taka", size)
    if "Bold" in font:
        # The Taka glyph only exists in a regular weight; a thin outline stroke makes it match bold digits.
        c.setStrokeColor(color)
        c.setLineWidth(size * .045)
        t.setTextRenderMode(2)
    t.textOut(settings.CURRENCY_SYMBOL)
    t.setTextRenderMode(0)
    c.drawText(t)
    c.setFont(font, size)
    c.drawString(x + pdfmetrics.stringWidth(settings.CURRENCY_SYMBOL, "Taka", size), y, text)
    c.restoreState()
    return w


def money_markup(value):
    return f'<font name="Taka">{settings.CURRENCY_SYMBOL}</font>{_amount(value)}'


def draw_ring(c, cx, cy, r, pct, tone, width, label=None, sub=None, label_size=13):
    """A progress ring: tinted track plus a coloured arc from 12 o'clock, clockwise."""
    c.saveState()
    c.setLineWidth(width)
    c.setLineCap(1)
    c.setStrokeColor(_tint(tone, .16))
    c.circle(cx, cy, r, stroke=1, fill=0)
    pct = max(0, min(100, pct or 0))
    if pct >= 100:
        c.setStrokeColor(tone)
        c.circle(cx, cy, r, stroke=1, fill=0)
    elif pct > 0:
        c.setStrokeColor(tone)
        p = c.beginPath()
        p.arc(cx - r, cy - r, cx + r, cy + r, startAng=90, extent=-360 * pct / 100)
        c.drawPath(p, stroke=1, fill=0)
    if label:
        c.setFillColor(INK)
        c.setFont("Inter-ExtraBold", label_size)
        c.drawCentredString(cx, cy - label_size * .1 + (3 if sub else -label_size * .25), label)
    if sub:
        c.setFillColor(INK3)
        c.setFont("Inter-SemiBold", 6.5)
        c.drawCentredString(cx, cy - 9, sub)
    c.restoreState()


LOGO = Path(__file__).resolve().parent / "assets" / "logo-light.png"   # hourglass logo, light outline for the dark header


def brand_mark(c, cx, cy, height):
    """The site's hourglass logo, centred on (cx, cy)."""
    w = height * 320 / 595
    c.drawImage(str(LOGO), cx - w / 2, cy - height / 2, width=w, height=height, mask="auto")


class Header(Flowable):
    def __init__(self, width, user, year, generated):
        super().__init__()
        self.width, self.height = width, 34 * mm
        self.user, self.year, self.generated = user, year, generated

    def draw(self):
        c = self.canv
        c.setFillColor(INK)
        c.roundRect(0, 0, self.width, self.height, 7 * mm, stroke=0, fill=1)
        brand_mark(c, 12 * mm, self.height - 11 * mm, 9 * mm)
        c.setFillColor(WHITE)
        c.setFont("Inter-ExtraBold", 12)
        c.drawString(17.5 * mm, self.height - 12.3 * mm, settings.SITE_NAME)
        c.setFont("Inter-ExtraBold", 22)
        c.drawString(8 * mm, 10.5 * mm, f"Impact report {self.year}")
        c.setFillColor(colors.HexColor("#aeb3bd"))
        c.setFont("Inter", 9)
        c.drawString(8 * mm, 5.5 * mm, f"{self.user.name}  ·  {self.user.email}")
        c.drawRightString(self.width - 8 * mm, 5.5 * mm, f"Generated {self.generated:%d %b %Y, %I:%M %p}")
        # lime pill, like the site's announcement bar button
        label = "Use it · Sell it · Don't lose it"
        w = pdfmetrics.stringWidth(label, "Inter-Bold", 8) + 8 * mm
        x = self.width - 8 * mm - w
        y = self.height - 14.5 * mm
        c.setStrokeColor(LIME)
        c.setLineWidth(1)
        c.roundRect(x, y, w, 7 * mm, 3.5 * mm, stroke=1, fill=0)
        c.setFillColor(LIME)
        c.setFont("Inter-Bold", 8)
        c.drawCentredString(x + w / 2, y + 2.4 * mm, label)


class Summary(Flowable):
    """Kept-out-of-the-bin headline with the overall ring and a share bar."""

    def __init__(self, width, summary, sections, item_count):
        super().__init__()
        self.width, self.height = width, 36 * mm
        self.summary, self.sections, self.count = summary, sections, item_count

    def draw(self):
        c = self.canv
        c.setFillColor(WHITE)
        c.setStrokeColor(LINE)
        c.roundRect(0, 0, self.width, self.height, 6 * mm, stroke=1, fill=1)
        rate = self.summary.rescue_rate if self.summary else 0
        rate = rate or 0
        tone = GREEN if rate >= 70 else (colors.HexColor("#d97706") if rate >= 40 else RED)
        draw_ring(c, 21 * mm, self.height / 2, 11 * mm, rate, tone, 7, f"{rate}%", "KEPT", 14)

        kept = self.summary.total_kept if self.summary else 0
        lost = self.summary.total_lost if self.summary else 0
        x = 40 * mm
        w = draw_money(c, x, self.height - 13 * mm, kept, "Inter-ExtraBold", 20)
        c.setFillColor(INK)
        c.setFont("Inter-Bold", 13)
        c.drawString(x + w + 2.5 * mm, self.height - 13 * mm, "kept out of the bin")
        c.setFillColor(INK2)
        c.setFont("Inter", 9)
        line = f"Earned plus saved, against "
        c.drawString(x, self.height - 19.5 * mm, line)
        lw = pdfmetrics.stringWidth(line, "Inter", 9)
        mw = draw_money(c, x + lw, self.height - 19.5 * mm, lost, "Inter", 9, INK2)
        c.setFillColor(INK2)
        c.setFont("Inter", 9)
        c.drawString(x + lw + mw, self.height - 19.5 * mm,
                     f" lost across {self.count} item{'s' if self.count != 1 else ''}.")

        # share bar
        bx, by, bw, bh = x, 8 * mm, self.width - x - 8 * mm, 3.2 * mm
        segs = [s for s in self.sections if s["share"]]
        if not segs:
            c.setFillColor(SURFACE2)
            c.roundRect(bx, by, bw, bh, bh / 2, stroke=0, fill=1)
        else:
            gap = 1.2 * mm
            avail = bw - gap * (len(segs) - 1)
            total = sum(s["share"] for s in segs)
            cur = bx
            for s in segs:
                sw = avail * s["share"] / total
                c.setFillColor(TONES[s["outcome"]])
                c.roundRect(cur, by, sw, bh, bh / 2, stroke=0, fill=1)
                cur += sw + gap
        # legend
        lx = bx
        c.setFont("Inter-SemiBold", 7.5)
        for s in self.sections:
            c.setFillColor(TONES[s["outcome"]])
            c.circle(lx + 1.2 * mm, by - 4 * mm + 1, 1.1 * mm, stroke=0, fill=1)
            c.setFillColor(INK2)
            t = f"{s['title']} {s['share']}%"
            c.drawString(lx + 3.4 * mm, by - 4 * mm, t)
            lx += pdfmetrics.stringWidth(t, "Inter-SemiBold", 7.5) + 9 * mm


class MetricCards(Flowable):
    """The three sections: ring on the left, amount on the right."""

    def __init__(self, width, sections):
        super().__init__()
        self.width, self.height = width, 40 * mm
        self.sections = sections

    def draw(self):
        c = self.canv
        gap = 4 * mm
        cw = (self.width - gap * 2) / 3
        for i, s in enumerate(self.sections):
            tone = TONES[s["outcome"]]
            x = i * (cw + gap)
            c.setFillColor(WHITE)
            c.setStrokeColor(LINE)
            c.roundRect(x, 0, cw, self.height, 5 * mm, stroke=1, fill=1)
            # icon chip + title
            c.setFillColor(_tint(tone, .14))
            c.roundRect(x + 5 * mm, self.height - 11.5 * mm, 6.5 * mm, 6.5 * mm, 1.8 * mm, stroke=0, fill=1)
            c.setFillColor(tone)
            c.circle(x + 8.25 * mm, self.height - 8.25 * mm, 1.3 * mm, stroke=0, fill=1)
            c.setFillColor(INK)
            c.setFont("Inter-Bold", 9.5)
            c.drawString(x + 13.5 * mm, self.height - 9.4 * mm, s["title"])
            # ring left
            draw_ring(c, x + 15 * mm, 13.5 * mm, 8.5 * mm, s["share"], tone, 5.5, f"{s['share']}%", "OF TOTAL", 10.5)
            # amount right
            draw_money(c, x + cw - 5 * mm, 15.5 * mm, s["total"], "Inter-ExtraBold", 17, tone, align="right")
            c.setFillColor(INK2)
            c.setFont("Inter-SemiBold", 8)
            c.drawRightString(x + cw - 5 * mm, 10 * mm, f"{s['count']} {s['noun']}")


def _footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Inter", 7.5)
    canvas.setFillColor(INK3)
    canvas.drawString(doc.leftMargin, 10 * mm, f"{settings.SITE_NAME} — track it, use it, or pass it on.")
    canvas.drawRightString(A4[0] - doc.rightMargin, 10 * mm, f"Page {doc.page}")
    canvas.restoreState()


def build_impact_pdf(user, year, summary, sections, records):
    _register_fonts()
    buf = BytesIO()
    margin = 14 * mm
    doc = SimpleDocTemplate(
        buf, pagesize=A4, leftMargin=margin, rightMargin=margin, topMargin=margin, bottomMargin=18 * mm,
        title=f"{settings.SITE_NAME} impact report {year}", author=user.name, subject="Impact report",
    )
    width = A4[0] - 2 * margin
    now = timezone.localtime()

    h2 = ParagraphStyle("h2", fontName="Inter-Bold", fontSize=13, leading=16, textColor=INK, spaceBefore=4, spaceAfter=6)
    body = ParagraphStyle("body", fontName="Inter", fontSize=8.5, leading=11, textColor=INK)
    muted = ParagraphStyle("muted", parent=body, textColor=INK3, fontSize=8)
    right = ParagraphStyle("right", parent=body, alignment=TA_RIGHT, fontName="Inter-Bold")
    head = ParagraphStyle("head", parent=body, fontName="Inter-SemiBold", textColor=INK3, fontSize=7.5)
    head_r = ParagraphStyle("head_r", parent=head, alignment=TA_RIGHT)

    story = [
        Header(width, user, year, now), Spacer(1, 6 * mm),
        Summary(width, summary, sections, len(records)), Spacer(1, 4 * mm),
        MetricCards(width, sections), Spacer(1, 8 * mm),
    ]

    story.append(Paragraph(f"All outcomes in {year}", h2))
    if records:
        rows = [[Paragraph("Date", head), Paragraph("Item", head), Paragraph("Outcome", head),
                 Paragraph("Notes", head), Paragraph("Value", head_r)]]
        style = [
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("LINEBELOW", (0, 0), (-1, 0), .8, LINE),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, SURFACE2]),
        ]
        for i, r in enumerate(records, start=1):
            tone = TONES[r.outcome]
            hexcol = tone.hexval().replace("0x", "#")
            rows.append([
                Paragraph(r.resolved_date.strftime("%d %b"), muted),
                Paragraph(f"<b>{_esc(r.item.item_name)}</b>", body),
                Paragraph(f'<font color="{hexcol}"><b>● {LABELS[r.outcome]}</b></font>', body),
                Paragraph(_esc(r.notes or "—"), muted),
                Paragraph(money_markup(r.amount_value), right),
            ])
        # totals row
        total = sum((r.amount_value for r in records), Decimal(0))
        rows.append(["", Paragraph("<b>Total tracked value</b>", body), "", "", Paragraph(money_markup(total), right)])
        style += [("LINEABOVE", (0, -1), (-1, -1), .8, INK), ("BACKGROUND", (0, -1), (-1, -1), WHITE)]
        t = Table(rows, colWidths=[17 * mm, 58 * mm, 22 * mm, width - 17 * mm - 58 * mm - 22 * mm - 26 * mm, 26 * mm],
                  repeatRows=1)
        t.setStyle(TableStyle(style))
        story.append(t)
    else:
        story.append(Paragraph(
            "Nothing resolved this year yet. When you sell an item, mark one as used, or something expires, "
            "it appears here.", muted))

    story.append(Spacer(1, 8 * mm))
    story.append(KeepTogether([
        Paragraph("How these numbers work", h2),
        Paragraph("<b>Earned from the shop</b> — what buyers paid for orders that were handed over.", body),
        Spacer(1, 2),
        Paragraph("<b>Lost in expiration</b> — the value of items that passed their expiry date while still in your list.", body),
        Spacer(1, 2),
        Paragraph("<b>Saved by using</b> — the value of items you marked as used before they expired.", body),
    ]))

    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return buf.getvalue()


def _esc(text):
    return (str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
