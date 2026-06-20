from django.urls import reverse
from django_tenants.test.cases import FastTenantTestCase
from django_tenants.test.client import TenantClient


class TenantEndpointTests(FastTenantTestCase):
    """Endpoint tests run inside a real tenant schema, routed by host.

    FastTenantTestCase spins up a throwaway tenant + schema; TenantClient
    sends requests with that tenant's host so TenantMainMiddleware resolves it.
    """

    @classmethod
    def get_test_tenant_domain(cls):
        # Must be allowed by ALLOWED_HOSTS (.localhost wildcard).
        return "test.localhost"

    @classmethod
    def get_test_schema_name(cls):
        return "test"

    def setUp(self):
        self.client = TenantClient(self.tenant)

    def test_health_is_public_and_ok(self):
        """Liveness probe returns 200 without authentication."""
        response = self.client.get(reverse("health"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")

    def test_unauthenticated_request_is_rejected_by_default(self):
        """DRF is secure-by-default: token refresh without creds must not 200."""
        response = self.client.post("/api/auth/token/refresh/", {})
        self.assertNotEqual(response.status_code, 200)
