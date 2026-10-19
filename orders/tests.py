from decimal import Decimal

from django.test import TestCase

from catalog.models import Category
from orders.models import Order, OrderItem, Refund, Return
from orders.services.order_service import (cancel_order,cancel_order_item,return_order, return_order_item, update_return_status,mark_cod_payment_collected,process_approved_return_refund,)
from products.models import Product
from users.models import User
from wallet.models import Wallet, WalletTransaction


class ReturnRefundCalculationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="return-refund@example.com",
            full_name="Return Refund",
            phone="1234567890",
            password="test-password",
        )
        pots = Category.objects.create(name="Pots")
        self.category = Category.objects.create(name="Planters", parent=pots)
        self.product = Product.objects.create(
            category=self.category,
            name="Ceramic planter",
            description="A ceramic planter",
            regular_price=Decimal("200.00"),
            stock_quantity=10,
    def create_order(
        self,
        order_number,
        *,
        include_second_item=True,
        status="DELIVERED",
        payment_status="PENDING",
        stock_deducted=False,
    ):
        item_prices = [Decimal("100.00")]
        if include_second_item:
            item_prices.append(Decimal("200.00"))
        subtotal = sum(item_prices, Decimal("0.00"))
        discount_amount = subtotal * Decimal("0.10")
        tax_amount = subtotal * Decimal("0.18")
        shipping_amount = Decimal("150.00")

        order = Order.objects.create(
            user=self.user,
            order_number=order_number,
            delivery_method="Standard",
            payment_method="Cash on Delivery",
            payment_status=payment_status,
            discount_amount=discount_amount,
            shipping_amount=shipping_amount,
            subtotal=subtotal,
            tax_amount=tax_amount,
            total_amount=subtotal + tax_amount + shipping_amount - discount_amount,
            status=status,
        )
        items = [
            OrderItem.objects.create(
                order=order,
                product=self.product,
                product_name=self.product.name,
                quantity=1,
                unit_price=item_price,
                total_price=item_price,
                stock_deducted=stock_deducted,
            )
            for item_price in item_prices
        ]
        if stock_deducted:
            self.product.stock_quantity -= len(items)
            self.product.save(update_fields=["stock_quantity"])

        return order, items[0], items[1] if len(items) > 1 else None

    def create_wallet(self, balance=Decimal("25.00")):
        return Wallet.objects.create(user=self.user, balance=balance)

    def test_bulk_return_calculates_tax_and_proportional_coupon_discount(self):
        order, item_100, item_200 = self.create_order("ORDER-BULK-RETURN")

        returned_order, error = return_order(
            user=self.user,
            order_number=order.order_number,
            return_reason="Changed mind",
        )

        self.assertIsNone(error)
        self.assertEqual(returned_order, order)
        self.assertEqual(
            Return.objects.get(order_item=item_100).refund_amount,
            Decimal("108.00"),
        )
        self.assertEqual(
            Return.objects.get(order_item=item_200).refund_amount,
            Decimal("216.00"),
        )
        self.assertEqual(
            sum(Return.objects.values_list("refund_amount", flat=True)),
            Decimal("324.00"),
        )

    def test_individual_return_uses_same_tax_and_discount_calculation(self):
        order, item_100, _ = self.create_order("ORDER-ITEM-RETURN")

        return_request, error = return_order_item(
            user=self.user,
            order_number=order.order_number,
            order_item_id=item_100.id,
            return_reason="Changed mind",
        )

        self.assertIsNone(error)
        self.assertEqual(return_request.refund_amount, Decimal("108.00"))
        self.assertNotEqual(return_request.refund_amount, order.shipping_amount)

    def test_full_order_cancellation_refunds_once_and_restores_stock_once(self):
        order, item_100, item_200 = self.create_order(
            "ORDER-FULL-CANCEL",
            status="PROCESSING",
            payment_status="PAID",
            stock_deducted=True,
        )
        wallet = self.create_wallet()

        cancelled_order, error = cancel_order(self.user, order.order_number)

        self.assertIsNone(error)
        self.assertEqual(cancelled_order.status, "CANCELLED")
        wallet.refresh_from_db()
        self.assertEqual(wallet.balance, Decimal("499.00"))
        transactions = WalletTransaction.objects.filter(wallet=wallet)
        self.assertEqual(transactions.count(), 1)
        self.assertEqual(transactions.get().transaction_type, "CREDIT")
        self.assertEqual(transactions.get().amount, Decimal("474.00"))
        self.assertFalse(Refund.objects.exists())
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 10)
        for item in (item_100, item_200):
            item.refresh_from_db()
            self.assertFalse(item.stock_deducted)

        repeated_order, repeated_error = cancel_order(self.user, order.order_number)

        self.assertIsNone(repeated_order)
        self.assertEqual(repeated_error, "This order cannot be cancelled.")
        wallet.refresh_from_db()
        self.product.refresh_from_db()
        self.assertEqual(wallet.balance, Decimal("499.00"))
        self.assertEqual(WalletTransaction.objects.filter(wallet=wallet).count(), 1)
        self.assertEqual(self.product.stock_quantity, 10)

    def test_last_item_cancellation_refunds_tax_coupon_and_shipping_once(self):
        order, item_100, _ = self.create_order(
            "ORDER-LAST-ITEM-CANCEL",
            include_second_item=False,
            status="PROCESSING",
            payment_status="PAID",
            stock_deducted=True,
        )
        wallet = self.create_wallet()

        cancelled_item, error = cancel_order_item(
            self.user,
            order.order_number,
            item_100.id,
        )

        self.assertIsNone(error)
        self.assertEqual(cancelled_item.item_status, "CANCELLED")
        wallet.refresh_from_db()
        self.assertEqual(wallet.balance, Decimal("283.00"))
        transaction_record = WalletTransaction.objects.get(wallet=wallet)
        self.assertEqual(transaction_record.transaction_type, "CREDIT")
        self.assertEqual(transaction_record.amount, Decimal("258.00"))
        self.product.refresh_from_db()
        item_100.refresh_from_db()
        order.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 10)
        self.assertFalse(item_100.stock_deducted)
        self.assertEqual(order.shipping_amount, Decimal("0.00"))

        repeated_item, repeated_error = cancel_order_item(
            self.user,
            order.order_number,
            item_100.id,
        )

        self.assertIsNone(repeated_item)
        self.assertEqual(repeated_error, "This order item cannot be cancelled.")
        wallet.refresh_from_db()
        self.product.refresh_from_db()
        self.assertEqual(wallet.balance, Decimal("283.00"))
        self.assertEqual(WalletTransaction.objects.filter(wallet=wallet).count(), 1)
        self.assertEqual(self.product.stock_quantity, 10)

    def test_return_approval_refunds_saved_amount_once_and_restores_stock_once(self):
        order, item_100, _ = self.create_order(
            "ORDER-RETURN-APPROVAL",
            include_second_item=False,
            payment_status="PAID",
            stock_deducted=True,
        )
        wallet = self.create_wallet()
        return_request, error = return_order_item(
            self.user,
            order.order_number,
            item_100.id,
            "Changed mind",
        )

        self.assertIsNone(error)
        self.assertEqual(return_request.refund_amount, Decimal("108.00"))
        _, error = update_return_status(return_request.id, "PICKED")
        self.assertIsNone(error)

        approved_return, error = update_return_status(
            return_request.id,
            "INSPECT_APPROVED",
        )

        self.assertIsNone(error)
        self.assertEqual(approved_return.status, "INSPECT_APPROVED")
        wallet.refresh_from_db()
        self.assertEqual(wallet.balance, Decimal("133.00"))
        transaction_record = WalletTransaction.objects.get(wallet=wallet)
        self.assertEqual(transaction_record.transaction_type, "CREDIT")
        self.assertEqual(transaction_record.amount, return_request.refund_amount)
        refund = Refund.objects.get(return_request=return_request)
        self.assertEqual(refund.amount, return_request.refund_amount)
        self.assertEqual(refund.status, "COMPLETED")
        self.assertNotEqual(refund.amount, order.shipping_amount)
        self.product.refresh_from_db()
        item_100.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 10)
        self.assertFalse(item_100.stock_deducted)

        repeated_return, repeated_error = update_return_status(
            return_request.id,
            "INSPECT_APPROVED",
        )

        self.assertIsNone(repeated_return)
        self.assertEqual(
            repeated_error,
            "Return cannot move from INSPECT_APPROVED to INSPECT_APPROVED.",
        )
        wallet.refresh_from_db()
        self.product.refresh_from_db()
        self.assertEqual(wallet.balance, Decimal("133.00"))
        self.assertEqual(WalletTransaction.objects.filter(wallet=wallet).count(), 1)
        self.assertEqual(Refund.objects.filter(return_request=return_request).count(), 1)
        self.assertEqual(self.product.stock_quantity, 10)


    def test_cod_payment_can_be_marked_paid_after_delivery(self):
        # Confirm COD collection marks a delivered pending order as paid.
        order, _, _ = self.create_order(
            "ORDER-COD-COLLECTED",
            payment_status="PENDING",
        )

        updated_order, error = mark_cod_payment_collected(order.order_number)

        self.assertIsNone(error)
        self.assertEqual(updated_order.payment_status, "PAID")

        order.refresh_from_db()
        self.assertEqual(order.payment_status, "PAID")
        self.assertEqual(order.status, "DELIVERED")


    def test_cod_collection_rejects_non_cod_order(self):
        # Prevent COD collection for orders using another payment method.
        order, _, _ = self.create_order(
            "ORDER-NON-COD",
            payment_status="PENDING",
        )
        order.payment_method = "Razorpay"
        order.save(update_fields=["payment_method"])

        updated_order, error = mark_cod_payment_collected(order.order_number)

        self.assertIsNone(updated_order)
        self.assertEqual(error, "This order is not Cash on Delivery")


    def test_cod_collection_rejects_undelivered_order(self):
        # Prevent COD collection before delivery.
        order, _, _ = self.create_order(
            "ORDER-NOT-DELIVERED",
            payment_status="PENDING",
        )
        order.status = "PLACED"
        order.save(update_fields=["status"])

        updated_order, error = mark_cod_payment_collected(order.order_number)

        self.assertIsNone(updated_order)
        self.assertEqual(error, "COD payment can only be collected after delivery")

    def test_cod_collection_rejects_already_paid_order(self):
        # Prevent collecting payment twice for the same order.
        order, _, _ = self.create_order(
            "ORDER-ALREADY-PAID",
            payment_status="PAID",
        )

        updated_order, error = mark_cod_payment_collected(order.order_number)

        self.assertIsNone(updated_order)
        self.assertEqual(error, "This order is already paid")


    def test_approved_return_refund_recovery_credits_wallet_once(self):
        # Recover an approved return refund without restoring stock twice.
        order, item, _ = self.create_order(
            "ORDER-REFUND-RECOVERY",
            include_second_item=False,
            payment_status="PAID",
            stock_deducted=True,
        )
        wallet = self.create_wallet()
        return_request, error = return_order_item(
            self.user,
            order.order_number,
            item.id,
            "Damaged item",
        )
        self.assertIsNone(error)

        _, error = update_return_status(return_request.id, "PICKED")
        self.assertIsNone(error)
        approved_return, error = update_return_status(
            return_request.id,
            "INSPECT_APPROVED",
        )
        self.assertIsNone(error)

        # Simulate a previously approved return whose refund was not created.
        Refund.objects.filter(return_request=approved_return).delete()
        wallet.refresh_from_db()
        balance_before = wallet.balance
        self.product.refresh_from_db()
        stock_before = self.product.stock_quantity

        refund, error = process_approved_return_refund(approved_return.id)

        self.assertIsNone(error)
        self.assertEqual(refund.status, "COMPLETED")
        self.assertEqual(refund.amount, Decimal("108.00"))

        wallet.refresh_from_db()
        self.product.refresh_from_db()
        self.assertEqual(wallet.balance, balance_before + Decimal("108.00"))
        self.assertEqual(self.product.stock_quantity, stock_before)

        # A repeated recovery must not credit the wallet again.
        repeated_refund, repeated_error = process_approved_return_refund(
            approved_return.id
        )
        self.assertIsNone(repeated_error)
        self.assertEqual(repeated_refund.id, refund.id)

        wallet.refresh_from_db()
        self.assertEqual(wallet.balance, balance_before + Decimal("108.00"))
        self.assertEqual(
            Refund.objects.filter(return_request=approved_return).count(),
            1,
        )

    def test_pending_refund_with_existing_wallet_credit_does_not_credit_twice(self):
        # Recover a pending refund when its wallet credit already exists.
        order, item, _ = self.create_order(
            "ORDER-PENDING-REFUND-EXISTING-CREDIT",
            include_second_item=False,
            payment_status="PAID",
        )
        wallet = self.create_wallet()
        return_request, error = return_order_item(
            self.user, order.order_number, item.id, "Damaged item"
        )
        self.assertIsNone(error)

        _, error = update_return_status(return_request.id, "PICKED")
        self.assertIsNone(error)
        _, error = update_return_status(return_request.id, "INSPECT_APPROVED")
        self.assertIsNone(error)

        refund = Refund.objects.get(return_request=return_request)
        transaction_id = f"RETURN-REFUND-{refund.id}"

        # Simulate an interrupted process after the wallet credit.
        Refund.objects.filter(pk=refund.pk).update(status="PENDING")
        wallet.refresh_from_db()
        balance_before = wallet.balance
        transaction_count_before = WalletTransaction.objects.count()

        recovered, error = process_approved_return_refund(return_request.id)

        self.assertIsNone(error)
        self.assertEqual(recovered.status, "COMPLETED")
        wallet.refresh_from_db()
        self.assertEqual(wallet.balance, balance_before)
        self.assertEqual(WalletTransaction.objects.count(), transaction_count_before)
        self.assertTrue(
            WalletTransaction.objects.filter(transaction_id=transaction_id).exists()
        )

    def test_pending_refund_without_wallet_credit_credits_once(self):
        # Recover a pending refund when no wallet credit exists.
        order, item, _ = self.create_order(
            "ORDER-PENDING-REFUND-NO-CREDIT",
            include_second_item=False,
            payment_status="PAID",
        )
        wallet = self.create_wallet()
        return_request, error = return_order_item(
            self.user, order.order_number, item.id, "Damaged item"
        )
        self.assertIsNone(error)

        _, error = update_return_status(return_request.id, "PICKED")
        self.assertIsNone(error)
        _, error = update_return_status(return_request.id, "INSPECT_APPROVED")
        self.assertIsNone(error)

        refund = Refund.objects.get(return_request=return_request)
        WalletTransaction.objects.filter(
            transaction_id=f"RETURN-REFUND-{refund.id}"
        ).delete()

        # Simulate a pending refund with its wallet credit missing.
        Refund.objects.filter(pk=refund.pk).update(
            status="PENDING",
            wallet_transaction_id=None,
            processed_at=None,
        )
        wallet.refresh_from_db()
        balance_before = wallet.balance

        recovered, error = process_approved_return_refund(return_request.id)

        self.assertIsNone(error)
        self.assertEqual(recovered.status, "COMPLETED")
        wallet.refresh_from_db()
        self.assertEqual(wallet.balance, balance_before + refund.amount)
        self.assertEqual(
            WalletTransaction.objects.filter(
                transaction_id=f"RETURN-REFUND-{refund.id}"
            ).count(),
            1,
        )
