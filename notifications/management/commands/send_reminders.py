from django.core.management.base import BaseCommand

from notifications.services import run_sweep


class Command(BaseCommand):
    help = "Send due expiry reminders and mark expired items/listings. Run daily from cron."

    def handle(self, *args, **options):
        result = run_sweep()
        self.stdout.write(
            self.style.SUCCESS(
                f"Sent {result['reminders_sent']} reminder(s); expired {result['items_expired']} item(s)."
            )
        )
