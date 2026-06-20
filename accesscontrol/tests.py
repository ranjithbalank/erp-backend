from django.contrib.auth.models import User
from django.db import connection
from django_tenants.test.cases import FastTenantTestCase
from rest_framework.test import APIClient

from .models import Department


class _TenantTestBase(FastTenantTestCase):
    @classmethod
    def get_test_tenant_domain(cls):
        return "test.localhost"  # allowed by ALLOWED_HOSTS (.localhost)

    @classmethod
    def get_test_schema_name(cls):
        return "test"


class DepartmentAPITests(_TenantTestBase):
    def setUp(self):
        self.user = User.objects.create_user("dep_user", "u@test.local", "pw-123456789")
        self.client = APIClient(HTTP_HOST=self.get_test_tenant_domain())
        self.client.force_authenticate(self.user)

    def test_create_department(self):
        resp = self.client.post(
            "/api/departments/", {"code": "dep-fin", "name": "Finance"}, format="json"
        )
        self.assertEqual(resp.status_code, 201, resp.content)
        # code is normalised to uppercase (DEP-02)
        self.assertEqual(resp.json()["code"], "DEP-FIN")
        self.assertTrue(Department.objects.filter(name="Finance").exists())

    def test_duplicate_code_rejected(self):
        Department.objects.create(code="DEP-HR", name="Human Resources")
        resp = self.client.post(
            "/api/departments/", {"code": "DEP-HR", "name": "HR Two"}, format="json"
        )
        self.assertEqual(resp.status_code, 400)

    def test_list_and_search(self):
        Department.objects.create(code="DEP-FIN", name="Finance")
        Department.objects.create(code="DEP-HR", name="Human Resources")
        resp = self.client.get("/api/departments/?search=Finance")
        self.assertEqual(resp.status_code, 200)
        names = [d["name"] for d in resp.json()]
        self.assertEqual(names, ["Finance"])

    def test_deactivate_then_activate(self):
        dept = Department.objects.create(code="DEP-OPS", name="Operations")
        d = self.client.post(f"/api/departments/{dept.id}/deactivate/")
        self.assertEqual(d.status_code, 200)
        self.assertFalse(d.json()["is_active"])
        a = self.client.post(f"/api/departments/{dept.id}/activate/")
        self.assertTrue(a.json()["is_active"])

    def test_delete_is_soft(self):
        dept = Department.objects.create(code="DEP-LEGACY", name="Legacy")
        resp = self.client.delete(f"/api/departments/{dept.id}/")
        self.assertEqual(resp.status_code, 204)
        dept.refresh_from_db()  # row still exists (DEP-05 spirit)
        self.assertFalse(dept.is_active)

    def test_self_parent_rejected(self):
        dept = Department.objects.create(code="DEP-X", name="Ex")
        resp = self.client.patch(f"/api/departments/{dept.id}/", {"parent": dept.id}, format="json")
        self.assertEqual(resp.status_code, 400)


class DepartmentAuthTests(_TenantTestBase):
    def test_unauthenticated_request_rejected(self):
        client = APIClient(HTTP_HOST=self.get_test_tenant_domain())
        resp = client.get("/api/departments/")
        self.assertIn(resp.status_code, (401, 403))


class DepartmentIsolationTests(_TenantTestBase):
    def test_department_table_is_tenant_only(self):
        """RULE #1: the table exists only inside tenant schemas, never public."""
        with connection.cursor() as cur:
            cur.execute(
                "select table_schema from information_schema.tables "
                "where table_name = 'accesscontrol_department'"
            )
            schemas = {r[0] for r in cur.fetchall()}
        self.assertIn("test", schemas)
        self.assertNotIn("public", schemas)
