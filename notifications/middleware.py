"""
Runs the reminder/expiry sweep lazily so the app works without a scheduler.

In development this means reminders fire as soon as anyone loads a page. In
production you can also (or instead) run `python manage.py send_reminders`
from cron once a day.
"""
from django.core.cache import cache

from .services import run_sweep

SWEEP_KEY = "shelflife:last-sweep"
SWEEP_INTERVAL_SECONDS = 60


class ReminderSweepMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.path.startswith(("/static/", "/admin/jsi18n")):
            if cache.add(SWEEP_KEY, True, SWEEP_INTERVAL_SECONDS):
                try:
                    run_sweep()
                except Exception:  # never break a page because of the sweep
                    cache.delete(SWEEP_KEY)
                    raise
        return self.get_response(request)
