from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase

from cart.models import Cart, CartItem
from catalog.models import Category
from orders.models import Order, OrderStatusHistory
from products.models import Product
from users.models import Address, User
from wallet.models import Wallet, WalletTransaction

from checkout.services.checkout_service import create_order


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
