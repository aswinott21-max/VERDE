from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from catalog.models import Category
from products.models import Product
from products.services.product_price_service import get_product_sale_price


class ProductSalePriceTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name="Test Category")
        self.product = Product.objects.create(
            category=self.category,
            name="Test Plant",
            description="Test description",
            regular_price=Decimal("100.00"),
        )
        self.now = timezone.now()

    @patch("products.services.product_price_service.timezone.now")
    def test_higher_category_offer_wins(self, mock_now):
        mock_now.return_value = self.now
        self.product.product_offer = Decimal("10")
        self.category.discount_value = Decimal("25")
        self.product.save()
        self.category.save()

        self.assertEqual(
            get_product_sale_price(self.product),
            Decimal("75.00"),
        )

    @patch("products.services.product_price_service.timezone.now")
    def test_higher_product_offer_wins(self, mock_now):
        mock_now.return_value = self.now
        self.product.product_offer = Decimal("30")
        self.category.discount_value = Decimal("15")
        self.product.save()
        self.category.save()

        self.assertEqual(
            get_product_sale_price(self.product),
            Decimal("70.00"),
        )

    @patch("products.services.product_price_service.timezone.now")
    def test_product_offer_applies_when_category_has_no_offer(self, mock_now):
        mock_now.return_value = self.now
        self.product.product_offer = Decimal("10")
        self.product.save()

        self.assertEqual(
            get_product_sale_price(self.product),
            Decimal("90.00"),
        )

    @patch("products.services.product_price_service.timezone.now")
    def test_category_offer_applies_when_product_has_no_offer(self, mock_now):
        mock_now.return_value = self.now
        self.category.discount_value = Decimal("25")
        self.category.save()

        self.assertEqual(
            get_product_sale_price(self.product),
            Decimal("75.00"),
        )

    @patch("products.services.product_price_service.timezone.now")
    def test_no_offer_returns_original_price(self, mock_now):
        mock_now.return_value = self.now

        self.assertEqual(
            get_product_sale_price(self.product),
            Decimal("100.00"),
        )

    @patch("products.services.product_price_service.timezone.now")
    def test_expired_offers_are_ignored(self, mock_now):
        mock_now.return_value = self.now
        expired_at = self.now - timedelta(days=1)

        self.product.product_offer = Decimal("30")
        self.product.offer_ends_at = expired_at
        self.category.discount_value = Decimal("25")
        self.category.offer_end_at = expired_at
        self.product.save()
        self.category.save()

        self.assertEqual(
            get_product_sale_price(self.product),
            Decimal("100.00"),
        )