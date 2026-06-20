from django.contrib.auth.models import User
from django.db import connection
from django_tenants.test.cases import FastTenantTestCase
from rest_framework.test import APIClient

from .models import Department, Employee, Role, UserProfile


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


class RoleTests(_TenantTestBase):
    def setUp(self):
        self.user = User.objects.create_user("role_admin", "r@test.local", "pw-123456789")
        self.client = APIClient(HTTP_HOST=self.get_test_tenant_domain())
        self.client.force_authenticate(self.user)

    def test_system_roles_seeded(self):
        names = set(Role.objects.filter(is_system=True).values_list("name", flat=True))
        self.assertEqual(names, {"Administrator", "Standard User"})

    def test_create_custom_role(self):
        resp = self.client.post("/api/roles/", {"name": "Auditor"}, format="json")
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertEqual(resp.json()["role_type"], "custom")
        self.assertFalse(resp.json()["is_system"])

    def test_system_role_cannot_be_edited_or_deleted(self):
        admin = Role.objects.get(name="Administrator")
        edit = self.client.patch(f"/api/roles/{admin.id}/", {"name": "X"}, format="json")
        self.assertEqual(edit.status_code, 400)
        delete = self.client.delete(f"/api/roles/{admin.id}/")
        self.assertEqual(delete.status_code, 400)

    def test_clone_system_role(self):
        admin = Role.objects.get(name="Administrator")
        resp = self.client.post(
            f"/api/roles/{admin.id}/clone/", {"name": "Admin Copy"}, format="json"
        )
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertFalse(resp.json()["is_system"])
        self.assertEqual(resp.json()["role_type"], "custom")

    def test_delete_role_assigned_to_user_blocked_rol06(self):
        role = Role.objects.create(name="Temp Role")
        u = User.objects.create_user("holder", "h@test.local", "pw-123456789")
        profile = UserProfile.objects.create(user=u)
        profile.roles.add(role)
        resp = self.client.delete(f"/api/roles/{role.id}/")
        self.assertEqual(resp.status_code, 400)  # ROL-06
        self.assertTrue(Role.objects.filter(id=role.id).exists())


class ProvisioningTests(_TenantTestBase):
    def setUp(self):
        self.user = User.objects.create_user("prov_admin", "p@test.local", "pw-123456789")
        self.client = APIClient(HTTP_HOST=self.get_test_tenant_domain())
        self.client.force_authenticate(self.user)
        self.dept = Department.objects.create(code="DEP-IT", name="IT")
        self.emp = Employee.objects.create(
            employee_code="EMP-100",
            first_name="Grace",
            last_name="Hopper",
            designation="Engineer",
            department=self.dept,
            work_email="grace@acme.test",
        )
        self.role = Role.objects.get(name="Standard User")

    def _provision(self, **over):
        payload = {"password": "TempPass123456", "role_ids": [self.role.id]}
        payload.update(over)
        return self.client.post(
            f"/api/employees/{self.emp.id}/provision-user/", payload, format="json"
        )

    def test_provision_success(self):
        resp = self._provision()
        self.assertEqual(resp.status_code, 201, resp.content)
        body = resp.json()
        self.assertEqual(body["status"], "invited")
        self.assertEqual(body["user"]["email"], "grace@acme.test")
        self.assertEqual([r["name"] for r in body["roles"]], ["Standard User"])
        self.emp.refresh_from_db()
        self.assertTrue(hasattr(self.emp, "user_profile"))

    def test_provision_requires_a_role_emp04(self):
        resp = self._provision(role_ids=[])
        self.assertEqual(resp.status_code, 400)

    def test_cannot_provision_twice(self):
        self.assertEqual(self._provision().status_code, 201)
        again = self._provision(username="dup", email="other@acme.test")
        self.assertEqual(again.status_code, 400)

    def test_unique_email_enforced_usr03(self):
        User.objects.create_user("taken", "grace@acme.test", "pw-123456789")
        resp = self._provision()
        self.assertEqual(resp.status_code, 400)
        self.assertIn("email", resp.json())

    def test_provisioned_user_can_authenticate(self):
        self.assertEqual(self._provision().status_code, 201)
        anon = APIClient(HTTP_HOST=self.get_test_tenant_domain())
        token = anon.post(
            "/api/auth/token/",
            {"username": "grace", "password": "TempPass123456"},
            format="json",
        )
        self.assertEqual(token.status_code, 200, token.content)
        self.assertIn("access", token.json())

    def test_deactivating_employee_disables_user_emp07(self):
        self.assertEqual(self._provision().status_code, 201)
        resp = self.client.post(f"/api/employees/{self.emp.id}/deactivate/")
        self.assertEqual(resp.status_code, 200)
        profile = UserProfile.objects.get(employee=self.emp)
        self.assertEqual(profile.status, "deactivated")
        self.assertFalse(profile.user.is_active)
