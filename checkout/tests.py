from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from cart.models import Cart, CartItem
from cart.services.cart_service import get_cart_details
from catalog.models import Category
from orders.models import Order, OrderStatusHistory
from products.models import Product
from users.models import Address, User
from wallet.models import Wallet, WalletTransaction

from checkout.services.checkout_service import (
    create_order,
    create_pending_razorpay_order,
    calculate_coupon_eligible_subtotal,
    validate_checkout_coupon,
)
from django.utils import timezone
from datetime import timedelta
from coupons.models import Coupon



class CreateOrderWalletPaymentTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="wallet-checkout@example.com",
            full_name="Wallet Checkout",
            phone="1234567890",
            password="test-password",
        )
        plants = Category.objects.create(name="Plants")
        category = Category.objects.create(name="Indoor", parent=plants)
        self.product = Product.objects.create(
            category=category,
            name="Monstera",
            description="Indoor plant",
            regular_price=Decimal("100.00"),
            stock_quantity=10,
        )
        self.address = Address.objects.create(
            user=self.user,
            address_label="Home",
            full_name=self.user.full_name,
            phone="1234567890",
            address_line1="1 Garden Lane",
            city="Greenville",
            state="CA",
            country="US",
            pin="12345",
        )
        self.cart = Cart.objects.create(user=self.user)
        self.cart_item = CartItem.objects.create(
            cart=self.cart,
            product=self.product,
            quantity=2,
            unit_price=Decimal("100.00"),
        )
        self.wallet = Wallet.objects.create(
            user=self.user,
            balance=Decimal("500.00"),
        )

    def place_order(self, payment_method="Wallet"):
        return create_order(
            user=self.user,
            address_id=self.address.id,
            delivery_method="Standard",
            payment_method=payment_method,
        )

    def test_wallet_payment_debits_exact_total_and_marks_order_paid(self):
        order, error = self.place_order()

        self.assertIsNone(error)
        self.assertEqual(order.payment_status, "PAID")
        self.assertEqual(order.total_amount, Decimal("350.00"))
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.balance, Decimal("150.00"))
        wallet_transaction = WalletTransaction.objects.get(
            transaction_id=f"ORDER-PAYMENT-{order.order_number}"
        )
        self.assertEqual(wallet_transaction.transaction_type, "DEBIT")
        self.assertEqual(wallet_transaction.amount, order.total_amount)
        self.assertEqual(wallet_transaction.reference_id, order.order_number)
        self.product.refresh_from_db()
        self.cart.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 8)
        self.assertFalse(self.cart.is_active)
        self.assertFalse(self.cart.items.exists())

    def test_insufficient_wallet_balance_leaves_checkout_unchanged(self):
        self.wallet.balance = Decimal("349.99")
        self.wallet.save(update_fields=["balance"])

        order, error = self.place_order()

        self.assertIsNone(order)
        self.assertEqual(error, "Insufficient wallet balance.")
        self.assertFalse(Order.objects.exists())
        self.assertFalse(WalletTransaction.objects.exists())
        self.wallet.refresh_from_db()
        self.product.refresh_from_db()
        self.cart.refresh_from_db()
        self.assertEqual(self.wallet.balance, Decimal("349.99"))
        self.assertEqual(self.product.stock_quantity, 10)
        self.assertTrue(self.cart.is_active)
        self.assertTrue(self.cart.items.filter(pk=self.cart_item.pk).exists())

    def test_invalid_payment_method_is_rejected_without_checkout_changes(self):
        for payment_method in ("Gift Card", []):
            order, error = self.place_order(payment_method=payment_method)

            self.assertIsNone(order)
            self.assertEqual(error, "Unsupported payment method.")
        self.assertFalse(Order.objects.exists())
        self.assertFalse(WalletTransaction.objects.exists())
        self.product.refresh_from_db()
        self.cart.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 10)
        self.assertTrue(self.cart.is_active)
        self.assertTrue(self.cart.items.filter(pk=self.cart_item.pk).exists())

    def test_later_failure_rolls_back_wallet_debit_and_checkout_changes(self):
        with patch.object(
            OrderStatusHistory.objects,
            "create",
            side_effect=RuntimeError("status history write failed"),
        ):
            with self.assertRaisesMessage(RuntimeError, "status history write failed"):
                self.place_order()

        self.assertFalse(Order.objects.exists())
        self.assertFalse(WalletTransaction.objects.exists())
        self.wallet.refresh_from_db()
        self.product.refresh_from_db()
        self.cart.refresh_from_db()
        self.assertEqual(self.wallet.balance, Decimal("500.00"))
        self.assertEqual(self.product.stock_quantity, 10)
        self.assertTrue(self.cart.is_active)
        self.assertTrue(self.cart.items.filter(pk=self.cart_item.pk).exists())

    def test_razorpay_order_remains_pending_without_wallet_debit(self):
        order, error = self.place_order(payment_method="Razorpay")

        self.assertIsNone(error)
        self.assertEqual(order.payment_status, "PENDING")
        self.assertFalse(WalletTransaction.objects.exists())
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.balance, Decimal("500.00"))

    def test_cash_on_delivery_order_remains_pending(self):
        order, error = self.place_order(payment_method="Cash on Delivery")

        self.assertIsNone(error)
        self.assertEqual(order.payment_status, "PENDING")
        self.assertFalse(WalletTransaction.objects.exists())


class CouponOfferEligibilityTests(TestCase):
    def setUp(self):
        now = timezone.now()

        self.user = User.objects.create_user(
            email="coupon-offer@example.com",
            full_name="Coupon Offer",
            phone="1234567891",
            password="test-password",
        )

        plants = Category.objects.create(name="Plants")
        self.category = Category.objects.create(name="Indoor", parent=plants)

        self.offered_product = Product.objects.create(
            category=self.category,
            name="Offered Plant",
            description="Plant with an active offer",
            regular_price=Decimal("200.00"),
            product_offer=Decimal("20.00"),
            offer_start_at=now - timedelta(days=1),
            offer_ends_at=now + timedelta(days=1),
            stock_quantity=10,
        )

        self.regular_product = Product.objects.create(
            category=self.category,
            name="Regular Plant",
            description="Plant without an offer",
            regular_price=Decimal("50.00"),
            stock_quantity=10,
        )

        self.coupon = Coupon.objects.create(
            code="ELIGIBLE10",
            coupon_name="Eligible Products Discount",
            discount_type="percentage",
            discount_value=Decimal("10.00"),
            minimum_order_amount=Decimal("0.00"),
            start_date=now - timedelta(days=1),
            expiry_date=now + timedelta(days=1),
            usage_limit=10,
            status="active",
        )

        self.address = Address.objects.create(
            user=self.user,
            address_label="Home",
            full_name=self.user.full_name,
            phone=self.user.phone,
            address_line1="1 Garden Lane",
            city="Greenville",
            state="CA",
            country="US",
            pin="12345",
        )
        self.client.force_login(self.user)

    def create_cart(self, *, include_offer=True, include_regular=False):
        cart = Cart.objects.create(user=self.user)
        if include_offer:
            CartItem.objects.create(
                cart=cart,
                product=self.offered_product,
                quantity=1,
                unit_price=self.offered_product.regular_price,
            )
        if include_regular:
            CartItem.objects.create(
                cart=cart,
                product=self.regular_product,
                quantity=1,
                unit_price=self.regular_product.regular_price,
            )
        return cart

    def apply_coupon(self):
        return self.client.post(
            reverse("cart:apply_coupon"),
            {"coupon_code": self.coupon.code},
        )

    def test_coupon_applies_to_cart_containing_only_offer_discounted_product(self):
        self.create_cart()

        cart_data = self.client.get(reverse("cart:view_cart")).json()
        response = self.apply_coupon()

        self.assertEqual(cart_data["subtotal"], "160.00")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["discount_amount"], "16.00")
        self.offered_product.refresh_from_db()
        self.assertEqual(self.offered_product.product_offer, Decimal("20.00"))

    def test_coupon_applies_to_mixed_offer_and_regular_price_cart(self):
        self.create_cart(include_regular=True)

        cart_data = self.client.get(reverse("cart:view_cart")).json()
        cart_items = list(self.user.carts.get(is_active=True).items.select_related("product"))
        coupon_subtotal = calculate_coupon_eligible_subtotal(
            (item.product, item.unit_price * item.quantity) for item in cart_items
        )

        coupon, discount, error = validate_checkout_coupon(
            self.coupon.code,
            coupon_subtotal,
            self.user,
        )

        self.assertEqual(cart_data["subtotal"], "210.00")
        self.assertEqual(coupon_subtotal, Decimal("210.00"))
        self.assertIsNone(error)
        self.assertEqual(coupon, self.coupon)
        self.assertEqual(discount, Decimal("21.00"))

    def test_minimum_spend_counts_discounted_price_but_not_tax_or_shipping(self):
        pots = Category.objects.create(name="Pots")
        pot_category = Category.objects.create(name="Planters", parent=pots)
        offered_pot = Product.objects.create(
            category=pot_category,
            name="Discounted Pot",
            description="A pot with an active offer",
            regular_price=Decimal("200.00"),
            product_offer=Decimal("20.00"),
            offer_start_at=timezone.now() - timedelta(days=1),
            offer_ends_at=timezone.now() + timedelta(days=1),
            stock_quantity=10,
        )
        cart = Cart.objects.create(user=self.user)
        CartItem.objects.create(
            cart=cart,
            product=offered_pot,
            quantity=1,
            unit_price=offered_pot.regular_price,
        )
        self.coupon.minimum_order_amount = Decimal("170.00")
        self.coupon.save(update_fields=["minimum_order_amount"])

        available = self.client.get(reverse("cart:available_coupons")).json()
        offered_coupon = next(item for item in available["coupons"] if item["code"] == self.coupon.code)
        response = self.apply_coupon()

        # Current product subtotal is 160; tax and shipping must not satisfy 170.
        self.assertFalse(offered_coupon["minimum_met"])
        self.assertEqual(offered_coupon["amount_needed"], "10.00")
        self.assertEqual(response.status_code, 400)
        self.assertIn("Minimum product subtotal", response.json()["message"])
        self.assertNotIn("checkout_coupon_id", self.client.session)

    def test_discounted_subtotal_can_meet_minimum_spend(self):
        self.create_cart()
        self.coupon.minimum_order_amount = Decimal("150.00")
        self.coupon.save(update_fields=["minimum_order_amount"])

        coupon_subtotal = calculate_coupon_eligible_subtotal([
            (self.offered_product, Decimal("160.00")),
        ])
        coupon, discount, error = validate_checkout_coupon(
            self.coupon.code,
            coupon_subtotal,
            self.user,
        )

        self.assertEqual(coupon_subtotal, Decimal("160.00"))
        self.assertEqual(coupon, self.coupon)
        self.assertEqual(discount, Decimal("16.00"))
        self.assertIsNone(error)

    def test_active_category_offer_price_is_coupon_eligible(self):
        now = timezone.now()
        self.category.discount_value = Decimal("15.00")
        self.category.offer_start_at = now - timedelta(days=1)
        self.category.offer_end_at = now + timedelta(days=1)
        self.category.save()

        eligible_subtotal = calculate_coupon_eligible_subtotal([
            (self.regular_product, Decimal("42.50")),
        ])

        coupon, discount, error = validate_checkout_coupon(
            self.coupon.code,
            eligible_subtotal,
            self.user,
        )

        self.assertEqual(eligible_subtotal, Decimal("42.50"))
        self.assertEqual(coupon, self.coupon)
        self.assertEqual(discount, Decimal("4.25"))
        self.assertIsNone(error)

    def test_coupon_preview_checkout_and_cod_order_totals_match(self):
        self.create_cart(include_regular=True)

        apply_response = self.apply_coupon()
        self.assertEqual(apply_response.status_code, 200)
        self.assertEqual(apply_response.json()["discount_amount"], "21.00")
        cart_items = self.client.get(reverse("cart:view_cart")).json()
        checkout_response = self.client.get(reverse("checkout:checkout"))
        self.assertEqual(checkout_response.context["coupon_discount"], Decimal("21.00"))

        order, error = create_order(
            user=self.user,
            address_id=self.address.pk,
            delivery_method="Standard",
            payment_method="Cash on Delivery",
            coupon_id=self.client.session["checkout_coupon_id"],
        )

        self.assertIsNone(error)
        self.assertEqual(order.subtotal, Decimal(cart_items["subtotal"]))
        self.assertEqual(order.discount_amount, Decimal("21.00"))
        self.assertEqual(order.shipping_amount, Decimal("150.00"))
        self.assertEqual(order.tax_amount, Decimal("0.00"))
        self.assertEqual(order.total_amount, Decimal("339.00"))
        self.assertEqual(
            order.total_amount,
            order.subtotal + order.tax_amount + order.shipping_amount - order.discount_amount,
        )

    def test_razorpay_order_uses_same_discounted_subtotal_and_coupon_total(self):
        self.create_cart(include_regular=True)
        cart_data = get_cart_details(self.user)
        item_totals = [
            (item["product"], item["item_total"])
            for item in cart_data["items"]
        ]
        expected_subtotal = calculate_coupon_eligible_subtotal(item_totals)
        coupon, expected_discount, error = validate_checkout_coupon(
            self.coupon.code,
            expected_subtotal,
            self.user,
        )
        self.assertIsNone(error)
        self.assertEqual(coupon, self.coupon)

        order, error = create_pending_razorpay_order(
            user=self.user,
            address_id=self.address.pk,
            delivery_method="Standard",
            coupon_id=self.coupon.pk,
        )

        self.assertIsNone(error)
        self.assertEqual(order.payment_status, "PENDING")
        self.assertEqual(order.subtotal, Decimal("210.00"))
        self.assertEqual(order.discount_amount, expected_discount)
        self.assertEqual(order.total_amount, Decimal("339.00"))

    def test_order_creation_recalculates_coupon_from_current_offer_price(self):
        self.create_cart(include_regular=True)
        apply_response = self.apply_coupon()
        self.assertEqual(apply_response.status_code, 200)
        self.assertEqual(apply_response.json()["discount_amount"], "21.00")

        # Repricing after application must not let order creation use the stale preview.
        self.offered_product.product_offer = Decimal("30.00")
        self.offered_product.save(update_fields=["product_offer"])
        order, error = create_order(
            user=self.user,
            address_id=self.address.pk,
            delivery_method="Standard",
            payment_method="Cash on Delivery",
            coupon_id=self.client.session["checkout_coupon_id"],
        )

        self.assertIsNone(error)
        self.assertEqual(order.subtotal, Decimal("190.00"))
        self.assertEqual(order.discount_amount, Decimal("19.00"))
        self.assertEqual(order.total_amount, Decimal("321.00"))
