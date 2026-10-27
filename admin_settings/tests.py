from django.test import TestCase
from django.urls import reverse
import json
from datetime import timedelta
from unittest.mock import patch

from django.utils import timezone

from users.models import User
from django.core.files.uploadedfile import SimpleUploadedFile


class AdminProfileUpdateTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create(
            email="settings-admin@example.com",
            full_name="Test Admin",
            phone=None,
            is_staff=True,
        )
        self.admin.set_password("TestPassword123!")
        self.admin.save()

        self.client.force_login(self.admin)
        self.url = reverse("admin_settings:update_admin_profile")

    def test_valid_profile_update(self):
        response = self.client.post(
            self.url,
            {
                "full_name": "Updated Admin",
                "phone": "9876543210",
            },
        )

        self.assertRedirects(
            response,
            reverse("admin_settings:admin_settings"),
        )

        self.admin.refresh_from_db()
        self.assertEqual(self.admin.full_name, "Updated Admin")
        self.assertEqual(self.admin.phone, "9876543210")


    def test_invalid_full_name_does_not_update_profile(self):
        # Invalid names must not modify the saved profile.
        response = self.client.post(
            self.url,
            {
                "full_name": "",
                "phone": "9876543210",
            },
        )

        self.assertRedirects(
            response,
            reverse("admin_settings:admin_settings"),
        )

        self.admin.refresh_from_db()
        self.assertEqual(self.admin.full_name, "Test Admin")

    def test_duplicate_phone_does_not_update_profile(self):
        User.objects.create(
            email="another-user@example.com",
            full_name="Another User",
            phone="9876543210",
        )

        response = self.client.post(
            self.url,
            {
                "full_name": "Updated Admin",
                "phone": "9876543210",
            },
        )

        self.assertRedirects(
            response,
            reverse("admin_settings:admin_settings"),
        )

        self.admin.refresh_from_db()
        self.assertEqual(self.admin.full_name, "Test Admin")
        self.assertIsNone(self.admin.phone)


    def test_unauthenticated_user_cannot_update_profile(self):
        self.client.logout()

        response = self.client.post(
            self.url,
            {
                "full_name": "Updated Admin",
                "phone": "9876543210",
            },
        )

        self.assertEqual(response.status_code, 302)

        self.admin.refresh_from_db()
        self.assertEqual(self.admin.full_name, "Test Admin")
        self.assertIsNone(self.admin.phone)

    def test_non_staff_user_cannot_update_profile(self):
        normal_user = User.objects.create(
            email="normal-user@example.com",
            full_name="Normal User",
            is_staff=False,
        )
        normal_user.set_password("TestPassword123!")
        normal_user.save()

        self.client.force_login(normal_user)

        response = self.client.post(
            self.url,
            {
                "full_name": "Updated Admin",
                "phone": "9876543210",
            },
        )

        self.assertEqual(response.status_code, 403)

        self.admin.refresh_from_db()
        self.assertEqual(self.admin.full_name, "Test Admin")
        self.assertIsNone(self.admin.phone)


    def test_profile_picture_update(self):
        image = SimpleUploadedFile(
            "profile.png",
            (
                b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
                b"\x00\x00\x00\x01\x00\x00\x00\x01"
                b"\x08\x02\x00\x00\x00\x90wS\xde"
                b"\x00\x00\x00\x0bIDAT\x08\xd7c\xf8"
                b"\xcf\xc0\x00\x00\x03\x01\x01\x00"
                b"\xc9\xfe\x92\xef\x00\x00\x00\x00IEND"
                b"\xaeB`\x82"
            ),
            content_type="image/png",
        )

        response = self.client.post(
            self.url,
            {
                "full_name": "Test Admin",
                "phone": "",
                "profile_picture": image,
            },
        )

        self.assertRedirects(
            response,
            reverse("admin_settings:admin_settings"),
        )

        self.admin.refresh_from_db()
        self.assertTrue(self.admin.profile_picture)



class AdminEmailChangeTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create(
            email="email-admin@example.com",
            full_name="Email Admin",
            is_staff=True,
        )
        self.client.force_login(self.admin)
        self.request_url = reverse("admin_settings:request_admin_email_change")
        self.verify_url = reverse("admin_settings:verify_admin_email_change")

    @patch("admin_settings.views.send_otp_email")
    def test_request_email_change_sends_otp(self, mock_send_otp):
        with patch("admin_settings.views.generate_otp", return_value=123456):
            response = self.client.post(
                self.request_url,
                data=json.dumps({"email": "new-admin@example.com"}),
                content_type="application/json",
            )

        self.assertEqual(response.status_code, 200)
        mock_send_otp.assert_called_once_with(
            "new-admin@example.com", 123456, "email_change"
        )
        self.assertEqual(
            self.client.session["admin_settings_email_change_data"]["email"],
            "new-admin@example.com",
        )

    
    @patch("admin_settings.views.send_otp_email")
    def test_email_otp_request_limit(self, mock_send_otp):
        # Allow three successful OTP sends, then block the fourth.
        with patch("admin_settings.views.generate_otp", return_value=123456):
            for _ in range(3):
                response = self.client.post(
                    self.request_url,
                    data=json.dumps({"email": "new-admin@example.com"}),
                    content_type="application/json",
                )
                self.assertEqual(response.status_code, 200)

            response = self.client.post(
                self.request_url,
                data=json.dumps({"email": "new-admin@example.com"}),
                content_type="application/json",
            )

        self.assertEqual(response.status_code, 429)
        self.assertEqual(mock_send_otp.call_count, 3)


    def test_duplicate_email_is_rejected(self):
        User.objects.create(
            email="already-used@example.com",
            full_name="Another User",
        )

        response = self.client.post(
            self.request_url,
            data=json.dumps({"email": "already-used@example.com"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)

    def test_invalid_otp_does_not_change_email(self):
        session = self.client.session
        session["admin_settings_email_change_data"] = {
            "user_id": self.admin.pk,
            "email": "new-admin@example.com",
            "otp": "123456",
            "expires_at": (timezone.now() + timedelta(seconds=60)).isoformat(),
        }
        session.save()

        response = self.client.post(
            self.verify_url,
            data=json.dumps({"otp": "000000"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.admin.refresh_from_db()
        self.assertEqual(self.admin.email, "email-admin@example.com")

    def test_expired_otp_is_rejected_and_session_cleared(self):
        session = self.client.session
        session["admin_settings_email_change_data"] = {
            "email": "new-admin@example.com",
            "otp": "123456",
            "expires_at": (timezone.now() - timedelta(seconds=60)).isoformat(),
        }
        session.save()

        response = self.client.post(
            self.verify_url,
            data=json.dumps({"otp": "123456"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertNotIn("admin_settings_email_change_data", self.client.session)

    def test_valid_otp_changes_email_and_clears_session(self):
        session = self.client.session
        session["admin_settings_email_change_data"] = {
            "user_id": self.admin.pk,
            "email": "new-admin@example.com",
            "otp": "123456",
            "expires_at": (timezone.now() + timedelta(seconds=60)).isoformat(),
        }
        session.save()

        response = self.client.post(
            self.verify_url,
            data=json.dumps({"otp": "123456"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.admin.refresh_from_db()
        self.assertEqual(self.admin.email, "new-admin@example.com")
        self.assertNotIn("admin_settings_email_change_data", self.client.session)

class AdminPasswordChangeTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create(
            email="password-admin@example.com",
            full_name="Password Admin",
            is_staff=True,
        )
        self.admin.set_password("OldPassword123!")
        self.admin.save()
        self.client.force_login(self.admin)

        self.send_url = reverse("admin_settings:send_admin_password_change_otp")
        self.verify_url = reverse("admin_settings:verify_admin_password_change_otp")
        self.change_url = reverse("admin_settings:change_admin_password")

    @patch("admin_settings.views.send_otp_email")
    def test_send_password_otp(self, mock_send_otp):
        with patch("admin_settings.views.generate_otp", return_value=123456):
            response = self.client.post(self.send_url)

        self.assertEqual(response.status_code, 200)
        mock_send_otp.assert_called_once_with(
            "password-admin@example.com", 123456, "password_change"
        )
        self.assertEqual(
            self.client.session["admin_settings_password_change_data"]["otp"],
            "123456",
        )

    
    @patch("admin_settings.views.send_otp_email")
    def test_password_otp_request_limit(self, mock_send_otp):
        # Allow three successful OTP sends, then block the fourth.
        with patch("admin_settings.views.generate_otp", return_value=123456):
            for _ in range(3):
                response = self.client.post(self.send_url)
                self.assertEqual(response.status_code, 200)

            response = self.client.post(self.send_url)

        self.assertEqual(response.status_code, 429)
        self.assertEqual(mock_send_otp.call_count, 3)


    def test_invalid_otp_is_rejected(self):
        session = self.client.session
        session["admin_settings_password_change_data"] = {
            "user_id": self.admin.pk,
            "otp": "123456",
            "expires_at": (timezone.now() + timedelta(seconds=60)).isoformat(),
        }
        session.save()

        response = self.client.post(
            self.verify_url,
            data=json.dumps({"otp": "000000"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertNotIn(
            "admin_settings_password_change_verified",
            self.client.session,
        )

    def test_expired_otp_is_rejected(self):
        session = self.client.session
        session["admin_settings_password_change_data"] = {
            "user_id": self.admin.pk,
            "otp": "123456",
            "expires_at": (timezone.now() - timedelta(seconds=60)).isoformat(),
        }
        session.save()

        response = self.client.post(
            self.verify_url,
            data=json.dumps({"otp": "123456"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertNotIn(
            "admin_settings_password_change_data",
            self.client.session,
        )

    def test_password_change_requires_verified_otp(self):
        response = self.client.post(
            self.change_url,
            data=json.dumps({
                "password": "NewPassword123!",
                "confirm_password": "NewPassword123!",
            }),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 403)
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.check_password("OldPassword123!"))

    def test_valid_otp_allows_password_change_and_clears_session(self):
        session = self.client.session
        session["admin_settings_password_change_data"] = {
            "user_id": self.admin.pk,
            "otp": "123456",
            "expires_at": (timezone.now() + timedelta(seconds=60)).isoformat(),
        }
        session["admin_settings_password_change_verified"] = True
        session.save()

        response = self.client.post(
            self.change_url,
            data=json.dumps({
                "password": "NewPassword123!",
                "confirm_password": "NewPassword123!",
            }),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.check_password("NewPassword123!"))
        self.assertNotIn(
            "admin_settings_password_change_data",
            self.client.session,
        )
        self.assertNotIn(
            "admin_settings_password_change_verified",
            self.client.session,
        )
