from django.test import TestCase
from django.urls import reverse


class HealthEndpointTests(TestCase):
    def test_health_is_public_and_ok(self):
        """Liveness probe returns 200 without authentication."""
        response = self.client.get(reverse("health"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")


class AuthDefaultsTests(TestCase):
    def test_unauthenticated_request_is_rejected_by_default(self):
        """DRF is secure-by-default: a protected endpoint needs auth.

        Hitting token refresh without credentials must not 200.
        """
        response = self.client.post("/api/auth/token/refresh/", {})
        self.assertNotEqual(response.status_code, 200)
