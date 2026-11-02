
import json
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser
from django.core.cache import cache
from django.test import TestCase, RequestFactory, override_settings

from chatbot.views import is_chatbot_rate_limited


@override_settings(
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        }
    }
)
class ChatbotRateLimitTests(TestCase):

    def setUp(self):
        self.factory = RequestFactory()
        cache.clear()

    def test_guest_limit(self):
        request = self.factory.post("/chatbot/chat/")
        request.user = AnonymousUser()

        for _ in range(5):
            self.assertFalse(is_chatbot_rate_limited(request))

        self.assertTrue(is_chatbot_rate_limited(request))

    def test_authenticated_user_limit(self):
        request = self.factory.post("/chatbot/chat/")
        request.user = SimpleNamespace(
            is_authenticated=True,
            id=123,
        )

        for _ in range(10):
            self.assertFalse(is_chatbot_rate_limited(request))

        self.assertTrue(is_chatbot_rate_limited(request))

    def test_users_have_separate_limits(self):
        guest_request = self.factory.post("/chatbot/chat/")
        guest_request.user = AnonymousUser()

        user_request = self.factory.post("/chatbot/chat/")
        user_request.user = SimpleNamespace(
            is_authenticated=True,
            id=123,
        )

        for _ in range(5):
            self.assertFalse(is_chatbot_rate_limited(guest_request))

        self.assertFalse(is_chatbot_rate_limited(user_request))

    @patch("chatbot.views.get_chat_response", return_value="Test response")
    @patch("chatbot.views.get_customer_order_context", return_value=None)
    def test_guest_endpoint_returns_429_after_limit(
        self, mock_order, mock_chat
    ):
        for _ in range(5):
            response = self.client.post(
                "/chatbot/chat/",
                data=json.dumps({"message": "Hello"}),
                content_type="application/json",
            )
            self.assertEqual(response.status_code, 200)

        response = self.client.post(
            "/chatbot/chat/",
            data=json.dumps({"message": "Hello"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 429)
        self.assertEqual(mock_chat.call_count, 5)
