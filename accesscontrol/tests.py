from django.contrib.auth.models import User
from django.db import connection
from django_tenants.test.cases import FastTenantTestCase
from rest_framework.test import APIClient

from .models import Department, Employee


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


class EmployeeAPITests(_TenantTestBase):
    def setUp(self):
        self.user = User.objects.create_user("emp_user", "e@test.local", "pw-123456789")
        self.client = APIClient(HTTP_HOST=self.get_test_tenant_domain())
        self.client.force_authenticate(self.user)
        self.dept = Department.objects.create(code="DEP-FIN", name="Finance")

    def test_register_employee(self):
        resp = self.client.post(
            "/api/employees/",
            {
                "employee_code": "emp-001",
                "first_name": "Ada",
                "last_name": "Lovelace",
                "designation": "Analyst",
                "department": self.dept.id,
                "work_email": "ada@acme.test",
            },
            format="json",
        )
        self.assertEqual(resp.status_code, 201, resp.content)
        body = resp.json()
        self.assertEqual(body["employee_code"], "EMP-001")  # normalised
        self.assertEqual(body["full_name"], "Ada Lovelace")

    def test_department_is_required(self):
        resp = self.client.post(
            "/api/employees/",
            {"employee_code": "EMP-002", "first_name": "A", "last_name": "B", "designation": "X"},
            format="json",
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("department", resp.json())

    def test_hr_only_employee_without_user_or_email(self):
        # EMP-06: an employee can exist without a work email / user account.
        resp = self.client.post(
            "/api/employees/",
            {
                "employee_code": "EMP-003",
                "first_name": "No",
                "last_name": "Email",
                "designation": "Clerk",
                "department": self.dept.id,
            },
            format="json",
        )
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertIsNone(resp.json()["work_email"])

    def test_delete_is_soft(self):
        emp = Employee.objects.create(
            employee_code="EMP-009",
            first_name="Soft",
            last_name="Del",
            designation="Temp",
            department=self.dept,
        )
        resp = self.client.delete(f"/api/employees/{emp.id}/")
        self.assertEqual(resp.status_code, 204)
        emp.refresh_from_db()
        self.assertFalse(emp.is_active)


class DepartmentEmployeeRulesTests(_TenantTestBase):
    """DEP-05 (delete guard) and DEP-06 (employee count)."""

    def setUp(self):
        self.user = User.objects.create_user("mgr", "m@test.local", "pw-123456789")
        self.client = APIClient(HTTP_HOST=self.get_test_tenant_domain())
        self.client.force_authenticate(self.user)
        self.dept = Department.objects.create(code="DEP-OPS", name="Operations")

    def test_employee_count_dep06(self):
        Employee.objects.create(
            employee_code="E1",
            first_name="A",
            last_name="A",
            designation="x",
            department=self.dept,
        )
        Employee.objects.create(
            employee_code="E2",
            first_name="B",
            last_name="B",
            designation="x",
            department=self.dept,
            is_active=False,
        )
        resp = self.client.get(f"/api/departments/{self.dept.id}/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["employee_count"], 1)  # active only

    def test_cannot_delete_department_with_active_employees_dep05(self):
        Employee.objects.create(
            employee_code="E3",
            first_name="C",
            last_name="C",
            designation="x",
            department=self.dept,
        )
        resp = self.client.delete(f"/api/departments/{self.dept.id}/")
        self.assertEqual(resp.status_code, 400)
        self.dept.refresh_from_db()
        self.assertTrue(self.dept.is_active)  # still active — not removed
