import functools
from decimal import Decimal, InvalidOperation

from django import template
from django.conf import settings
from django.contrib.humanize.templatetags.humanize import intcomma

register = template.Library()


@register.filter
def money(value):
    """৳1,250 or ৳62.50 — drops .00 for whole amounts."""
    try:
        value = Decimal(value or 0)
    except (InvalidOperation, TypeError):
        return value
    text = f"{value:,.0f}" if value == value.to_integral() else f"{value:,.2f}"
    return f"{settings.CURRENCY_SYMBOL}{text}"


@register.inclusion_tag("partials/_ring.html")
def freshness_ring(item, size="md"):
    return {"item": item, "size": size}


@register.inclusion_tag("partials/_field.html")
def field(bound_field, hint=None):
    return {"f": bound_field, "hint": hint}


@register.filter
def stars(value):
    try:
        n = int(round(float(value)))
    except (TypeError, ValueError):
        return ""
    return "★" * n + "☆" * (5 - n)


@register.simple_tag(takes_context=True)
def active(context, *prefixes):
    path = context["request"].path
    return "is-active" if any(path.startswith(p) for p in prefixes) else ""


# Small SF-Symbols-like line icons (24px grid, 1.8 stroke).
ICONS = {
    "bell": '<path d="M6 8a6 6 0 1 1 12 0c0 7 3 9 3 9H3s3-2 3-9"/><path d="M10.3 21a1.94 1.94 0 0 0 3.4 0"/>',
    "home": '<path d="M3 10.5 12 3l9 7.5"/><path d="M5 9.5V20a1 1 0 0 0 1 1h4v-6h4v6h4a1 1 0 0 0 1-1V9.5"/>',
    "box": '<path d="M21 8 12 3 3 8v8l9 5 9-5z"/><path d="m3 8 9 5 9-5M12 13v8"/>',
    "bag": '<path d="M5 8h14l-1 13H6z"/><path d="M9 8V6a3 3 0 0 1 6 0v2"/>',
    "leaf": '<path d="M11 20A7 7 0 0 1 4 13c0-6 5-10 16-10 0 11-4 16-9 17z"/><path d="M4 21c3-5 6-8 11-11"/>',
    "plus": '<path d="M12 5v14M5 12h14"/>',
    "search": '<circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/>',
    "check": '<path d="m5 12.5 4.5 4.5L19 7"/>',
    "x": '<path d="M6 6l12 12M18 6 6 18"/>',
    "info": '<circle cx="12" cy="12" r="9"/><path d="M12 11v5M12 8h.01"/>',
    "clock": '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    "tag": '<path d="M3 12V4a1 1 0 0 1 1-1h8l9 9-9 9z"/><circle cx="7.5" cy="7.5" r="1.5"/>',
    "card": '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="M3 10h18"/>',
    "star": '<path d="m12 3 2.8 5.7 6.2.9-4.5 4.4 1 6.2L12 17.3 6.5 20.2l1-6.2L3 9.6l6.2-.9z"/>',
    "pin": '<path d="M12 21s-7-6.2-7-11.5a7 7 0 0 1 14 0C19 14.8 12 21 12 21z"/><circle cx="12" cy="9.5" r="2.5"/>',
    "chevron-left": '<path d="m15 18-6-6 6-6"/>',
    "trash": '<path d="M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3"/>',
    "edit": '<path d="M4 20h4L19 9l-4-4L4 16z"/><path d="m13.5 6.5 4 4"/>',
    "alert": '<path d="M12 3 2 20h20z"/><path d="M12 10v4M12 17h.01"/>',
    "receipt": '<path d="M6 3h12v18l-3-2-3 2-3-2-3 2z"/><path d="M9 8h6M9 12h6"/>',
    "sun": '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
    "moon": '<path d="M20 14.5A8 8 0 0 1 9.5 4 8 8 0 1 0 20 14.5z"/>',
    "menu": '<path d="M4 7h16M4 12h16M4 17h16"/>',
    "share": '<path d="M12 3v12M8 7l4-4 4 4"/><path d="M5 12v7a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-7"/>',
    "grid": '<circle cx="7" cy="7" r="3"/><circle cx="17" cy="7" r="3"/><circle cx="7" cy="17" r="3"/><circle cx="17" cy="17" r="3"/>',
    "chart": '<path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/>',
    "user": '<circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/>',
    "store": '<path d="M4 9 5.5 4h13L20 9"/><path d="M4 9a2.7 2.7 0 0 0 5.3 0 2.7 2.7 0 0 0 5.4 0 2.7 2.7 0 0 0 5.3 0"/><path d="M5 10.5V20h14v-9.5M10 20v-5h4v5"/>',
    "logout": '<path d="M15 4h3a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2h-3M10 17l5-5-5-5M15 12H4"/>',
    "settings": '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3h0a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8v0a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"/>',
    "chevron-down": '<path d="m6 9 6 6 6-6"/>',
    "chevron-right": '<path d="m9 6 6 6-6 6"/>',
    "sparkle": '<path d="M12 3c.6 4.6 2.4 6.4 7 7-4.6.6-6.4 2.4-7 7-.6-4.6-2.4-6.4-7-7 4.6-.6 6.4-2.4 7-7z"/><path d="M19 15c.2 1.6.9 2.3 2.5 2.5-1.6.2-2.3.9-2.5 2.5-.2-1.6-.9-2.3-2.5-2.5 1.6-.2 2.3-.9 2.5-2.5z"/>',
    "camera": '<path d="M4 8h3l2-3h6l2 3h3a1 1 0 0 1 1 1v10a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V9a1 1 0 0 1 1-1z"/><circle cx="12" cy="13.5" r="3.5"/>',
    "download": '<path d="M12 4v11M7 10.5l5 5 5-5"/><path d="M5 20h14"/>',
    "qr": '<rect x="3.5" y="3.5" width="6.5" height="6.5" rx="1.2"/><rect x="14" y="3.5" width="6.5" height="6.5" rx="1.2"/><rect x="3.5" y="14" width="6.5" height="6.5" rx="1.2"/><path d="M14 14h3v3h-3zM20.5 14v.01M17 20.5h3.5V17M14 20.5h.01"/>',
    "shield": '<path d="M12 3 4 6v6c0 5 3.5 8 8 9 4.5-1 8-4 8-9V6z"/>',
}


@register.simple_tag
def icon(name, label=None):
    from django.utils.safestring import mark_safe
    body = ICONS.get(name, "")
    aria = f'role="img" aria-label="{label}"' if label else 'aria-hidden="true"'
    return mark_safe(
        f'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" '
        f'stroke-linecap="round" stroke-linejoin="round" {aria}>{body}</svg>'
    )


@register.simple_tag
def avatar(user, size=""):
    """A user's profile picture, or their initials when they haven't uploaded one."""
    from django.utils.html import format_html

    cls = f"avatar avatar--{size}" if size else "avatar"
    if getattr(user, "avatar", None):
        return format_html('<img class="{} avatar--img" src="{}" alt="" loading="lazy">', cls, user.avatar.url)
    return format_html('<span class="{}">{}</span>', cls, user.initials)


@register.filter
def photo_url(f):
    """URL of an ImageField, or '' when it's empty (avoids .url errors in templates)."""
    try:
        return f.url if f else ""
    except ValueError:
        return ""


@functools.lru_cache(maxsize=64)
def _find_static(path):
    """Where a static file lives on disk (looked up once; the file's date is still read every time)."""
    from django.contrib.staticfiles import finders

    return finders.find(path)


@register.simple_tag
def asset(path):
    """Static URL with a version stamp (?v=<last-modified>) so browsers never use an old copy."""
    import os

    from django.templatetags.static import static

    url = static(path)
    found = _find_static(path)
    if found:
        try:
            url += f"?v={int(os.path.getmtime(found))}"
        except OSError:                      # file moved since it was looked up
            _find_static.cache_clear()
    return url
