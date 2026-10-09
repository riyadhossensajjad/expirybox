from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from impact.models import ImpactRecord, ImpactSummary, OutcomeStatus
from notifications.models import Notification, Reminder
from notifications.services import run_sweep, schedule_reminders

from .models import Category, Item, ItemStatus


class ItemTests(TestCase):
    def setUp(self):
        self.today = timezone.localdate()
        self.user = User.objects.create_user(email="a@example.com", password="pass12345!", name="Ana Tester")
        self.client.force_login(self.user)

    def test_categories_are_seeded(self):
        self.assertTrue(Category.objects.filter(category_name="Medicine").exists())

    def test_create_item_schedules_reminders(self):
        r = self.client.post(reverse("items:create"), {
            "item_name": "Milk", "price": "95", "expiry_date": (self.today + timedelta(days=10)).isoformat(),
        })
        item = Item.objects.get(item_name="Milk")
        self.assertRedirects(r, item.get_absolute_url())
        dates = sorted(item.reminders.values_list("reminder_date", flat=True))
        self.assertEqual([(d - self.today).days for d in dates], [3, 7, 9, 10])

    def test_item_close_to_expiry_gets_reminder_today(self):
        item = Item.objects.create(user=self.user, item_name="Bread", expiry_date=self.today + timedelta(days=2))
        schedule_reminders(item)
        self.assertTrue(item.reminders.filter(reminder_date=self.today).exists())
        run_sweep()
        self.assertTrue(Notification.objects.filter(user=self.user, item=item, notification_type="EXPIRY").exists())
        self.assertFalse(Reminder.objects.filter(item=item, reminder_date=self.today, is_sent=False).exists())

    def test_sweep_expires_items_and_records_loss(self):
        item = Item.objects.create(user=self.user, item_name="Cheese", expiry_date=self.today - timedelta(days=1))
        run_sweep()
        item.refresh_from_db()
        self.assertEqual(item.status, ItemStatus.EXPIRED)
        self.assertTrue(ImpactRecord.objects.filter(item=item, outcome=OutcomeStatus.LOST).exists())

    def test_mark_used_records_saving(self):
        item = Item.objects.create(user=self.user, item_name="Rice", expiry_date=self.today + timedelta(days=30))
        self.client.post(reverse("items:mark_used", args=[item.pk]), {"amount_value": "350"})
        item.refresh_from_db()
        self.assertEqual(item.status, ItemStatus.USED)
        summary = ImpactSummary.objects.get(user=self.user, year=self.today.year)
        self.assertEqual(summary.total_saved, Decimal("350"))

    def test_users_only_see_their_own_items(self):
        other = User.objects.create_user(email="o@example.com", password="pass12345!", name="Other")
        item = Item.objects.create(user=other, item_name="Secret", expiry_date=self.today)
        self.assertEqual(self.client.get(item.get_absolute_url()).status_code, 404)
        self.assertNotContains(self.client.get(reverse("items:list")), "Secret")

    def test_purchase_after_expiry_is_rejected(self):
        r = self.client.post(reverse("items:create"), {
            "item_name": "Odd", "price": "1", "expiry_date": self.today.isoformat(),
            "purchase_date": (self.today + timedelta(days=1)).isoformat(),
        })
        self.assertEqual(r.status_code, 200)
        self.assertFalse(Item.objects.filter(item_name="Odd").exists())

    def test_all_pages_render(self):
        item = Item.objects.create(user=self.user, item_name="Tea", expiry_date=self.today + timedelta(days=5))
        for name, args in [
            ("items:dashboard", []), ("items:list", []), ("items:create", []),
            ("items:detail", [item.pk]), ("items:update", [item.pk]), ("items:delete", [item.pk]),
            ("notifications:list", []), ("impact:overview", []), ("marketplace:browse", []),
            ("marketplace:selling", []), ("marketplace:buying", []), ("marketplace:listing_create", [item.pk]),
            ("accounts:profile", []), ("accounts:seller", [self.user.pk]),
        ]:
            self.assertEqual(self.client.get(reverse(name, args=args)).status_code, 200, name)


class AccountTests(TestCase):
    def test_signup_logs_in(self):
        r = self.client.post(reverse("accounts:signup"), {
            "name": "New Person", "email": "new@example.com", "phone": "", "address": "Banani",
            "password1": "freshly-Kept-42", "password2": "freshly-Kept-42",
        })
        self.assertRedirects(r, reverse("items:create"))
        self.assertTrue(User.objects.filter(email="new@example.com").exists())

    def test_login_with_email(self):
        User.objects.create_user(email="l@example.com", password="pass12345!", name="L")
        r = self.client.post(reverse("accounts:login"), {"username": "l@example.com", "password": "pass12345!"})
        self.assertRedirects(r, reverse("items:dashboard"))

    def test_anonymous_pages(self):
        for url in ["/", reverse("accounts:login"), reverse("accounts:signup"), reverse("marketplace:browse")]:
            self.assertEqual(self.client.get(url).status_code, 200, url)
        self.assertEqual(self.client.get(reverse("items:dashboard")).status_code, 302)


class NotificationFeedTests(TestCase):
    def test_feed_returns_unread_after_id(self):
        from notifications.services import notify
        user = User.objects.create_user(email="f@example.com", password="pass12345!", name="Feed User")
        self.client.force_login(user)
        a = notify(user, "First")
        b = notify(user, "Second")
        data = self.client.get(reverse("notifications:feed"), {"after": a.pk}).json()
        self.assertEqual(data["unread"], 2)
        self.assertEqual([n["id"] for n in data["items"]], [b.pk])
        self.assertEqual(data["items"][0]["message"], "Second")



def _png_upload(name="photo.png", size=(60, 40)):
    from io import BytesIO
    from django.core.files.uploadedfile import SimpleUploadedFile
    from PIL import Image
    buf = BytesIO()
    Image.new("RGBA", size, (30, 160, 80, 255)).save(buf, "PNG")
    return SimpleUploadedFile(name, buf.getvalue(), content_type="image/png")


class PhotoAndPriceTests(TestCase):
    def setUp(self):
        import tempfile
        from django.test import override_settings
        self._media = override_settings(MEDIA_ROOT=tempfile.mkdtemp())
        self._media.enable()
        self.addCleanup(self._media.disable)
        self.today = timezone.localdate()
        self.user = User.objects.create_user(email="p@example.com", password="pass12345!", name="Pia Photo")
        self.client.force_login(self.user)

    def test_price_is_required(self):
        r = self.client.post(reverse("items:create"), {
            "item_name": "No price", "expiry_date": self.today.isoformat(),
        })
        self.assertEqual(r.status_code, 200)
        self.assertFalse(Item.objects.filter(item_name="No price").exists())

    def test_item_with_photo_and_price(self):
        self.client.post(reverse("items:create"), {
            "item_name": "Honey", "price": "450", "expiry_date": (self.today + timedelta(days=90)).isoformat(),
            "image": _png_upload(),
        })
        item = Item.objects.get(item_name="Honey")
        self.assertEqual(item.price, Decimal("450"))
        self.assertTrue(item.image.name.endswith(".jpg"))  # converted and shrunk
        self.assertContains(self.client.get(item.get_absolute_url()), item.image.url)

    def test_remove_photo(self):
        self.client.post(reverse("items:create"), {
            "item_name": "Jam", "price": "200", "expiry_date": (self.today + timedelta(days=30)).isoformat(),
            "image": _png_upload(),
        })
        item = Item.objects.get(item_name="Jam")
        self.client.post(reverse("items:update", args=[item.pk]), {
            "item_name": "Jam", "price": "200", "expiry_date": item.expiry_date.isoformat(), "remove_photo": "on",
        })
        item.refresh_from_db()
        self.assertFalse(item.image)

    def test_rejects_non_image(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        r = self.client.post(reverse("items:create"), {
            "item_name": "Bad", "price": "1", "expiry_date": self.today.isoformat(),
            "image": SimpleUploadedFile("x.png", b"not an image", content_type="image/png"),
        })
        self.assertEqual(r.status_code, 200)
        self.assertFalse(Item.objects.filter(item_name="Bad").exists())

    def test_profile_picture_upload(self):
        self.client.post(reverse("accounts:profile"), {
            "save_profile": "1", "name": "Pia Photo", "email": "p@example.com", "phone": "", "address": "",
            "avatar": _png_upload("me.png"),
        })
        self.user.refresh_from_db()
        self.assertTrue(self.user.avatar)
        self.assertContains(self.client.get(reverse("items:dashboard")), self.user.avatar.url)


class SuggestTests(TestCase):
    def test_suggestions_are_own_items_with_price(self):
        today = timezone.localdate()
        me = User.objects.create_user(email="s@example.com", password="pass12345!", name="Sue")
        other = User.objects.create_user(email="o2@example.com", password="pass12345!", name="Other")
        Item.objects.create(user=me, item_name="Greek yogurt", price=220, expiry_date=today + timedelta(days=2))
        Item.objects.create(user=me, item_name="Frozen yogurt bar", price=90, expiry_date=today + timedelta(days=9))
        Item.objects.create(user=other, item_name="Yogurt (not mine)", price=1, expiry_date=today)
        self.client.force_login(me)
        data = self.client.get(reverse("items:suggest"), {"q": "yog"}).json()
        names = [r["name"] for r in data["results"]]
        self.assertEqual(names, ["Greek yogurt", "Frozen yogurt bar"])
        self.assertEqual(data["results"][0]["price"], "৳220")
        self.assertEqual(data["total"], 2)
        self.assertEqual(self.client.get(reverse("items:suggest"), {"q": ""}).json()["results"], [])


class QrAndCelebrateTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="q@example.com", password="pass12345!", name="Qui")
        self.client.force_login(self.user)

    def test_qr_label_is_svg_with_item_details(self):
        import json
        from .views import qr_payload
        item = Item.objects.create(user=self.user, item_name="Honey", price=450,
                                   expiry_date=timezone.localdate() + timedelta(days=60), reference_number="L-9")
        data = json.loads(qr_payload(item))
        self.assertEqual(data["name"], "Honey")
        self.assertEqual(data["batch"], "L-9")
        r = self.client.get(reverse("items:qr", args=[item.pk]))
        self.assertEqual(r["Content-Type"], "image/svg+xml")
        self.assertIn(b"<svg", r.content)

    def test_adding_an_item_shows_the_tick_once(self):
        r = self.client.post(reverse("items:create"), {
            "item_name": "Tea", "price": "300", "expiry_date": (timezone.localdate() + timedelta(days=30)).isoformat(),
        }, follow=True)
        self.assertContains(r, "data-celebrate")
        self.assertContains(r, "Item added")
        self.assertNotContains(self.client.get(reverse("items:list")), "data-celebrate")

    def test_add_page_has_qr_scanner(self):
        r = self.client.get(reverse("items:create"))
        self.assertContains(r, "data-qr")
        self.assertContains(r, "qr-scan.js")



class ImpactPdfTests(TestCase):
    def test_pdf_export(self):
        from impact.models import OutcomeStatus
        from impact.services import record_outcome
        user = User.objects.create_user(email="pdf@example.com", password="pass12345!", name="Pat Pdf")
        item = Item.objects.create(user=user, item_name="Rice <5kg> & co", price=900, expiry_date=timezone.localdate())
        record_outcome(item, OutcomeStatus.SAVED, amount=900)
        self.client.force_login(user)
        r = self.client.get(reverse("impact:export_pdf"), {"year": timezone.localdate().year})
        self.assertEqual(r["Content-Type"], "application/pdf")
        self.assertTrue(r.content.startswith(b"%PDF"))
        self.assertIn("attachment", r["Content-Disposition"])
