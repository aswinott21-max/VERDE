import json
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import SESSION_KEY
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from users.models import User
from users.services.auth_service import hash_user_password


class SignupOtpFlowTests(TestCase):
    signup_payload = {
        "name": "Test Customer",
        "email": "customer@example.test",
        "phone": "9876543210",
        "password": "StrongPass1!",
        "confirm_password": "StrongPass1!",
    }

    def set_signup_session(self, *, otp="123456", expires_at=None):
        session = self.client.session
        session["signup_data"] = {
            "name": self.signup_payload["name"],
            "email": self.signup_payload["email"],
            "phone": self.signup_payload["phone"],
            "referral_code": "",
            "password": hash_user_password(self.signup_payload["password"]),
            "otp": otp,
            "otp_expires_at": (expires_at or timezone.now() + timedelta(minutes=1)).isoformat(),
        }
        session.save()

    def post_json(self, url_name, payload):
        return self.client.post(
            reverse(url_name),
            data=json.dumps(payload),
            content_type="application/json",
        )

    @patch("users.views.send_otp_email")
    def test_valid_signup_otp_creates_and_logs_in_user_then_returns_home_destination(self, send_otp):
        signup_response = self.post_json("signup", self.signup_payload)

        self.assertEqual(signup_response.status_code, 200)
        self.assertEqual(signup_response.json()["message"], "OTP generated successfully")
        send_otp.assert_called_once()
        otp = self.client.session["signup_data"]["otp"]
        self.assertFalse(User.objects.filter(email=self.signup_payload["email"]).exists())

        verify_response = self.post_json("verify_otp", {"otp": otp})
        self.assertEqual(verify_response.status_code, 200)
        self.assertEqual(verify_response.json()["message"], "Email verified successfully")
        self.assertFalse(User.objects.filter(email=self.signup_payload["email"]).exists())

        create_response = self.post_json("create_account", {})

        self.assertEqual(create_response.status_code, 201)
        self.assertEqual(create_response.json()["redirect_url"], "/")
        user = User.objects.get(email=self.signup_payload["email"])
        self.assertTrue(user.is_verified)
        self.assertTrue(user.check_password(self.signup_payload["password"]))
        self.assertEqual(self.client.session[SESSION_KEY], str(user.pk))
        self.assertNotIn("signup_data", self.client.session)
        self.assertNotIn("verified_signup_email", self.client.session)
        self.assertEqual(self.client.get(reverse("dashboard")).status_code, 200)

    def test_invalid_otp_does_not_create_or_authenticate_user(self):
        self.set_signup_session()

        response = self.post_json("verify_otp", {"otp": "654321"})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "Invalid OTP")
        create_response = self.post_json("create_account", {})
        self.assertEqual(create_response.status_code, 400)
        self.assertFalse(User.objects.filter(email=self.signup_payload["email"]).exists())
        self.assertNotIn(SESSION_KEY, self.client.session)

    def test_expired_otp_does_not_create_or_authenticate_user(self):
        self.set_signup_session(expires_at=timezone.now() - timedelta(seconds=1))

        response = self.post_json("verify_otp", {"otp": "123456"})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "OTP has expired. Please request a new OTP.")
        create_response = self.post_json("create_account", {})
        self.assertEqual(create_response.status_code, 400)
        self.assertFalse(User.objects.filter(email=self.signup_payload["email"]).exists())
        self.assertNotIn(SESSION_KEY, self.client.session)

    @patch("users.views.send_otp_email")
    def test_new_signup_cannot_reuse_previous_signup_otp_verification(self, send_otp):
        signup_a = self.post_json("signup", self.signup_payload)
        self.assertEqual(signup_a.status_code, 200)
        otp_a = self.client.session["signup_data"]["otp"]
        verify_a = self.post_json("verify_otp", {"otp": otp_a})
        self.assertEqual(verify_a.status_code, 200)
        self.assertEqual(
            self.client.session["verified_signup_email"],
            self.signup_payload["email"],
        )

        signup_b_payload = {
            **self.signup_payload,
            "email": "second-customer@example.test",
            "phone": "9876543211",
        }
        signup_b = self.post_json("signup", signup_b_payload)
        self.assertEqual(signup_b.status_code, 200)
        otp_b = self.client.session["signup_data"]["otp"]
        self.assertNotIn("verified_signup_email", self.client.session)

        premature_create = self.post_json("create_account", {})
        self.assertEqual(premature_create.status_code, 400)
        self.assertFalse(User.objects.filter(email=signup_b_payload["email"]).exists())
        self.assertNotIn(SESSION_KEY, self.client.session)

        verify_b = self.post_json("verify_otp", {"otp": otp_b})
        self.assertEqual(verify_b.status_code, 200)
        create_b = self.post_json("create_account", {})
        self.assertEqual(create_b.status_code, 201)
        self.assertTrue(User.objects.filter(email=signup_b_payload["email"]).exists())
        send_otp.assert_any_call(signup_b_payload["email"], otp_b, "signup")

    def test_existing_signup_validation_still_rejects_missing_fields(self):
        response = self.post_json("signup", {"email": self.signup_payload["email"]})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "All fields are required")
        self.assertNotIn("signup_data", self.client.session)
