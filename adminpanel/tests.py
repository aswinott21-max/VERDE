from django.test import TestCase, override_settings
from django.urls import reverse

from users.models import User


@override_settings(DEBUG=False, ALLOWED_HOSTS=["testserver"])
class AdminDashboardAuthorizationTests(TestCase):
    def setUp(self):
        self.customer = User.objects.create_user(
            email="customer@example.test",
            full_name="VERDÉ Customer",
            phone="1000000001",
            password="test-password",
        )
        self.admin = User.objects.create_user(
            email="admin@example.test",
            full_name="VERDÉ Admin",
            phone="1000000002",
            password="test-password",
            is_staff=True,
        )

    def test_customer_receives_customer_403_page_for_admin_dashboard(self):
        self.client.force_login(self.customer)

        response = self.client.get(reverse("admin_dashboard_page"))

        self.assertEqual(response.status_code, 403)
        self.assertTemplateUsed(response, "403.html")
        self.assertContains(response, "Access Denied", status_code=403)

    def test_unauthenticated_user_keeps_admin_login_redirect(self):
        response = self.client.get(reverse("admin_dashboard_page"))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response["Location"],
            "/admin-login/?next=/adminpanel/admin-dashboard/",
        )

    def test_admin_can_access_dashboard(self):
        self.client.force_login(self.admin)

        response = self.client.get(reverse("admin_dashboard_page"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "adminpanel/admin_dashboard.html")

    def test_customer_still_receives_json_403_from_admin_api(self):
        self.client.force_login(self.customer)

        response = self.client.get(
            reverse("get_product_edit_data", args=[1]),
            HTTP_ACCEPT="application/json",
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response["Content-Type"], "application/json")
        self.assertEqual(
            response.json(),
            {"error": "You are not authorized to access this page"},
        )
