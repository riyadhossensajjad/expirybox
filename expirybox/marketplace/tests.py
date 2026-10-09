from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from impact.models import ImpactSummary
from items.models import Item, ItemStatus

from . import services
from .models import Listing, ListingStatus, OrderStatus, Payment


class MarketplaceFlowTests(TestCase):
    def setUp(self):
        self.today = timezone.localdate()
        self.seller = User.objects.create_user(email="s@example.com", password="pass12345!", name="Sam Seller")
        self.buyer = User.objects.create_user(email="b@example.com", password="pass12345!", name="Bina Buyer")
        self.item = Item.objects.create(user=self.seller, item_name="Yogurt", price=200, expiry_date=self.today + timedelta(days=3))

    def _list(self, qty=2):
        self.client.force_login(self.seller)
        self.client.post(reverse("marketplace:listing_create", args=[self.item.pk]), {
            "original_price": "200", "sale_price": "120", "quantity": qty,
            "pickup_location": "Dhanmondi", "available_until": self.item.expiry_date.isoformat(),
        })
        return Listing.objects.get(item=self.item)

    def test_listing_marks_item_listed(self):
        listing = self._list()
        self.item.refresh_from_db()
        self.assertEqual(listing.status, ListingStatus.ACTIVE)
        self.assertEqual(self.item.status, ItemStatus.LISTED)
        self.assertEqual(listing.discount_pct, 40)

    def test_sale_price_above_original_is_rejected(self):
        self.client.force_login(self.seller)
        r = self.client.post(reverse("marketplace:listing_create", args=[self.item.pk]), {
            "original_price": "100", "sale_price": "150", "quantity": 1,
            "pickup_location": "x", "available_until": self.item.expiry_date.isoformat(),
        })
        self.assertEqual(r.status_code, 200)
        self.assertFalse(Listing.objects.exists())

    def test_full_order_lifecycle(self):
        listing = self._list(qty=2)

        self.client.force_login(self.buyer)
        r = self.client.post(listing.get_absolute_url(), {"quantity": 2, "delivery_method": "PICKUP"})
        order = self.buyer.orders.get()
        self.assertRedirects(r, reverse("marketplace:order_pay", args=[order.pk]))
        self.assertEqual(order.total_price, Decimal("240"))
        listing.refresh_from_db(); self.item.refresh_from_db()
        self.assertEqual(listing.status, ListingStatus.SOLD)
        self.assertEqual(self.item.status, ItemStatus.SOLD)
        self.assertTrue(self.seller.notifications.filter(order=order).exists())

        self.client.post(reverse("marketplace:order_pay", args=[order.pk]), {"method": Payment.Method.BKASH})
        order.refresh_from_db()
        self.assertEqual(order.status, OrderStatus.PAID)
        self.assertEqual(order.payment.amount, Decimal("240"))

        self.client.force_login(self.seller)
        self.client.post(reverse("marketplace:order_action", args=[order.pk, "complete"]))
        order.refresh_from_db()
        self.assertEqual(order.status, OrderStatus.COMPLETED)
        summary = ImpactSummary.objects.get(user=self.seller, year=self.today.year)
        self.assertEqual(summary.total_earned, Decimal("240"))

        self.client.force_login(self.buyer)
        self.client.post(reverse("marketplace:review_create", args=[order.pk]), {"rating": 4, "comment": "Good"})
        self.assertEqual(self.seller.seller_rating, 4.0)

    def test_cannot_buy_own_listing_or_more_than_stock(self):
        listing = self._list(qty=1)
        with self.assertRaises(ValidationError):
            services.place_order(listing.pk, self.seller, 1, "PICKUP")
        with self.assertRaises(ValidationError):
            services.place_order(listing.pk, self.buyer, 5, "PICKUP")

    def test_cancel_returns_stock(self):
        listing = self._list(qty=1)
        order = services.place_order(listing.pk, self.buyer, 1, "PICKUP")
        services.cancel_order(order, self.buyer)
        listing.refresh_from_db(); self.item.refresh_from_db()
        self.assertEqual(listing.quantity, 1)
        self.assertEqual(listing.status, ListingStatus.ACTIVE)
        self.assertEqual(self.item.status, ItemStatus.LISTED)

    def test_refund_after_payment(self):
        listing = self._list(qty=1)
        order = services.place_order(listing.pk, self.buyer, 1, "PICKUP")
        services.pay_order(order, Payment.Method.CARD)
        services.refund_order(order)
        order.refresh_from_db()
        self.assertEqual(order.status, OrderStatus.REFUNDED)
        self.assertEqual(order.payment.status, Payment.Status.REFUNDED)

    def test_other_users_cannot_see_order(self):
        listing = self._list(qty=1)
        order = services.place_order(listing.pk, self.buyer, 1, "PICKUP")
        stranger = User.objects.create_user(email="x@example.com", password="pass12345!", name="X")
        self.client.force_login(stranger)
        self.assertEqual(self.client.get(order.get_absolute_url()).status_code, 404)

    def test_take_down_listing_returns_item_to_active(self):
        listing = self._list()
        self.client.post(reverse("marketplace:listing_cancel", args=[listing.pk]))
        listing.refresh_from_db(); self.item.refresh_from_db()
        self.assertEqual(listing.status, ListingStatus.CANCELLED)
        self.assertEqual(self.item.status, ItemStatus.ACTIVE)

    def test_seller_account_can_be_deleted_with_orders(self):
        listing = self._list(qty=1)
        services.place_order(listing.pk, self.buyer, 1, "PICKUP")
        self.seller.delete()
        self.assertFalse(Listing.objects.exists())


    def test_item_reaches_buyer_list_only_after_handover(self):
        listing = self._list(qty=2)
        order = services.place_order(listing.pk, self.buyer, 2, "PICKUP")
        services.pay_order(order, Payment.Method.BKASH)
        self.assertFalse(self.buyer.items.exists())  # paid, but not picked up yet
        services.complete_order(order)
        copy = self.buyer.items.get()
        self.assertEqual(copy.item_name, "2 × Yogurt")
        self.assertEqual(copy.expiry_date, self.item.expiry_date)
        self.assertEqual(copy.price, Decimal("240"))
        self.assertEqual(copy.status, ItemStatus.ACTIVE)
        self.assertTrue(copy.reminders.exists())
        order.refresh_from_db()
        self.assertEqual(order.buyer_item, copy)
        self.assertEqual(copy.purchase_order, order)

    def test_buyer_can_confirm_pickup(self):
        listing = self._list(qty=1)
        order = services.place_order(listing.pk, self.buyer, 1, "PICKUP")
        services.pay_order(order, Payment.Method.CASH)
        self.client.force_login(self.buyer)
        self.client.post(reverse("marketplace:order_action", args=[order.pk, "complete"]))
        order.refresh_from_db()
        self.assertEqual(order.status, OrderStatus.COMPLETED)
        self.assertTrue(self.buyer.items.filter(item_name="Yogurt").exists())
        self.assertTrue(self.seller.notifications.filter(message__contains="confirmed they received").exists())

    def test_refunded_order_never_reaches_buyer_list(self):
        listing = self._list(qty=1)
        order = services.place_order(listing.pk, self.buyer, 1, "PICKUP")
        services.pay_order(order, Payment.Method.CARD)
        services.refund_order(order)
        self.assertFalse(self.buyer.items.exists())

    def test_listing_form_prefills_item_price(self):
        self.client.force_login(self.seller)
        r = self.client.get(reverse("marketplace:listing_create", args=[self.item.pk]))
        self.assertContains(r, 'value="200')
