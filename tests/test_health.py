"""Basic endpoint and authentication-boundary tests."""

from django.test import TestCase
from django.urls import reverse


class HealthAndAuthenticationTests(TestCase):
    def test_health_endpoint_is_non_sensitive_and_available(self):
        response = self.client.get(reverse("health"))

        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(response.content, {"status": "ok"})

    def test_dashboard_requires_authentication(self):
        response = self.client.get(reverse("tasks:dashboard"))

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response.url)
