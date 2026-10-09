"""
Fill the database with demo users, items and listings so every screen has data.

    python manage.py seed_demo          # adds demo data (safe to re-run)
    python manage.py seed_demo --reset  # deletes the demo users first

All demo accounts use the password:  shelflife123
"""
from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils import timezone

from accounts.models import User
from impact.models import OutcomeStatus
from impact.services import record_outcome
from items.models import Category, Item, ItemStatus
from marketplace import services as market
from marketplace.models import Listing, Payment
from notifications.services import run_sweep, schedule_reminders

PASSWORD = "shelflife123"

# Value of items that aren't listed (listed ones use their original price).
PRICES = {"Greek yogurt, 500 g": 220, "Paracetamol 500 mg (strip of 10)": 25, "Mango juice, 1 L": 160, "AA batteries (8-pack)": 480}

USERS = [
    ("Ayesha Rahman", "ayesha@example.com", "+880 1711-000001", "Dhanmondi 27, Dhaka"),
    ("Tanvir Hasan", "tanvir@example.com", "+880 1811-000002", "Mirpur 10, Dhaka"),
    ("Nusrat Jahan", "nusrat@example.com", "+880 1911-000003", "Uttara Sector 7, Dhaka"),
]

# (owner index, name, category, days until expiry, days since purchase, provider, list price, sale price, qty)
ITEMS = [
    (0, "Greek yogurt, 500 g", "Dairy & eggs", 2, 10, "Shwapno", None, None, 0),
    (0, "Paracetamol 500 mg (strip of 10)", "Medicine", 40, 300, "Lazz Pharma", None, None, 0),
    (0, "Whole wheat bread", "Bakery", 1, 4, "Cooper's", "120", "60", 1),
    (0, "Basmati rice, 5 kg", "Groceries", 25, 160, "Meena Bazar", "1150", "900", 1),
    (0, "Vitamin C serum", "Personal care", 12, 200, "Shajgoj", "1450", "950", 1),
    (0, "Mango juice, 1 L", "Beverages", 5, 30, "Pran", None, None, 0),
    (1, "Mozzarella cheese, 200 g", "Dairy & eggs", 4, 20, "Unimart", "420", "280", 2),
    (1, "Frozen chicken nuggets", "Frozen", 6, 60, "Aftab", "520", "350", 1),
    (1, "Infant formula, 400 g", "Baby care", 18, 120, "Nestlé", "1350", "990", 3),
    (1, "Oat biscuits, family pack", "Bakery", 3, 50, "Olympic", "180", "110", 4),
    (2, "Fresh strawberries, 250 g", "Fruit & vegetables", 2, 2, "Chaldal", "350", "200", 2),
    (2, "Cold coffee cans (6-pack)", "Beverages", 9, 80, "Starbucks", "900", "620", 1),
    (2, "AA batteries (8-pack)", "Household", 60, 400, "Panasonic", None, None, 0),
    (2, "Sunscreen SPF 50", "Personal care", 20, 300, "Neutrogena", "1600", "1100", 1),
]


class Command(BaseCommand):
    help = "Create demo users, items, listings, orders and notifications."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="Delete existing demo users first.")

    def handle(self, *args, reset=False, **options):
        emails = [u[1] for u in USERS]
        if reset:
            User.objects.filter(email__in=emails).delete()

        if User.objects.filter(email__in=emails).exists():
            self.stdout.write("Demo data already exists. Use --reset to rebuild it.")
            return

        today = timezone.localdate()
        users = []
        for name, email, phone, address in USERS:
            users.append(User.objects.create_user(email=email, password=PASSWORD, name=name, phone=phone, address=address))

        cats = {c.category_name: c for c in Category.objects.all()}
        created = []
        for owner, name, cat, days, age, provider, orig, sale, qty in ITEMS:
            item = Item.objects.create(
                user=users[owner],
                category=cats.get(cat),
                item_name=name,
                provider=provider,
                purchase_date=today - timedelta(days=age),
                expiry_date=today + timedelta(days=days),
                reference_number=f"LOT-{1000 + len(created)}",
                price=Decimal(orig) if orig else PRICES.get(name, 0),
            )
            schedule_reminders(item)
            if orig:
                Listing.objects.create(
                    item=item, seller=users[owner], original_price=Decimal(orig), sale_price=Decimal(sale),
                    quantity=qty, pickup_location=users[owner].address, available_until=item.expiry_date,
                )
                item.status = ItemStatus.LISTED
                item.save(update_fields=["status"])
            created.append(item)

        # History for the impact page: one used, one already expired, one completed sale.
        used = Item.objects.create(
            user=users[0], category=cats.get("Fruit & vegetables"), item_name="Spinach bunch",
            provider="Agora", purchase_date=today - timedelta(days=6), expiry_date=today - timedelta(days=1), price=60,
            status=ItemStatus.USED,
        )
        record_outcome(used, OutcomeStatus.SAVED, amount=60, notes="Used before it expired.",
                       resolved_date=today - timedelta(days=2))
        Item.objects.create(
            user=users[0], category=cats.get("Dairy & eggs"), item_name="Sour cream, 200 g",
            provider="Shwapno", purchase_date=today - timedelta(days=20), expiry_date=today - timedelta(days=3), price=180,
        )

        # Tanvir buys Ayesha's rice; Nusrat buys Tanvir's biscuits and leaves a review.
        rice = Listing.objects.get(item__item_name__startswith="Basmati")
        order = market.place_order(rice.pk, users[1], 1, "PICKUP")
        market.pay_order(order, Payment.Method.BKASH)

        biscuits = Listing.objects.get(item__item_name__startswith="Oat biscuits")
        sale = market.place_order(biscuits.pk, users[2], 2, "DELIVERY")
        market.pay_order(sale, Payment.Method.CARD)
        market.complete_order(sale)
        sale.refresh_from_db()
        from marketplace.models import Review
        Review.objects.create(order=sale, reviewer=users[2], seller=users[1], rating=5,
                              comment="Well within date and Tanvir dropped them off the same evening.")

        market.place_order(Listing.objects.get(item__item_name__startswith="Fresh straw").pk, users[0], 1, "PICKUP")

        result = run_sweep()
        self.stdout.write(self.style.SUCCESS(
            f"Created {len(users)} users and {Item.objects.count()} items; "
            f"{result['reminders_sent']} reminders fired, {result['items_expired']} item(s) expired.\n"
            f"Sign in as {USERS[0][1]} / {PASSWORD}"
        ))
