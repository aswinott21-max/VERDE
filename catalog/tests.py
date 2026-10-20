from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from catalog.models import Category


class CategoryOfferValidationTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_user(
            email="offer_admin@example.com",
            full_name="Offer Admin",
            phone="9876543210",
            password="test-password-123",
            is_staff=True,
        )
        self.client.force_login(self.admin)
        self.category = Category.objects.create(name="Test Category")
        self.url = reverse(
            "set_category_offer",
            kwargs={"category_id": self.category.id},
        )

    def post_offer(self, discount="10", start="", end=""):
        return self.client.post(
            self.url,
            {
                "discount_value": discount,
                "offer_start_at": start,
                "offer_end_at": end,
            },
        )

    def test_valid_offer_is_saved(self):
        # Provide valid future dates required by the offer view.
        start = (timezone.now() + timedelta(hours=1)).strftime(
            "%Y-%m-%dT%H:%M"
        )
        end = (timezone.now() + timedelta(days=2)).strftime(
            "%Y-%m-%dT%H:%M"
        )
        response = self.post_offer(start=start, end=end)

        self.assertEqual(response.status_code, 200)
        self.category.refresh_from_db()
        self.assertEqual(self.category.discount_value, Decimal("10"))

    def test_past_start_date_is_rejected(self):
        past = (timezone.now() - timedelta(days=1)).strftime(
            "%Y-%m-%dT%H:%M"
        )

        response = self.post_offer(start=past)

        self.assertEqual(response.status_code, 400)

    def test_end_before_start_is_rejected(self):
        now = timezone.now()
        start = (now + timedelta(days=2)).strftime("%Y-%m-%dT%H:%M")
        end = (now + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M")

        response = self.post_offer(start=start, end=end)

        self.assertEqual(response.status_code, 400)

    def test_discount_above_100_is_rejected(self):
        response = self.post_offer(discount="101")

        self.assertEqual(response.status_code, 400)

    def test_offer_can_be_removed(self):
        self.category.discount_value = Decimal("10")
        self.category.save()

        response = self.client.post(
            self.url,
            {"remove_offer": "true"},
        )

        self.assertEqual(response.status_code, 200)
        self.category.refresh_from_db()
        self.assertEqual(self.category.discount_value, Decimal("0"))
        self.assertIsNone(self.category.offer_start_at)
        self.assertIsNone(self.category.offer_end_at)