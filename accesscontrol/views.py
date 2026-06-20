from django.db.models import Count, Q
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Department, Employee
from .serializers import DepartmentSerializer, EmployeeSerializer


class DepartmentViewSet(viewsets.ModelViewSet):
    """Department master CRUD (DEP-01/02/03/05/06).

    Access control is server-side (RULE #2): authentication is required and the
    queryset is tenant-scoped. Tenant scoping here is structural — the table
    lives in the tenant's own schema — so there is no cross-tenant queryset to
    leak. `get_queryset` is still defined explicitly per CLAUDE.md §6.
    """

    serializer_class = DepartmentSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["code", "name"]
    ordering_fields = ["code", "name", "created_at"]

    def get_queryset(self):
        # DEP-06: annotate the active-employee count for every row.
        qs = Department.objects.annotate(
            employee_count=Count("employees", filter=Q(employees__is_active=True))
        )
        is_active = self.request.query_params.get("is_active")
        if is_active is not None:
            qs = qs.filter(is_active=is_active.lower() in ("1", "true", "yes"))
        return qs

    def _guard_active_employees(self, dept):
        # DEP-05: a department with active employees may not be removed/deactivated.
        if dept.employees.filter(is_active=True).exists():
            raise ValidationError("Cannot deactivate or delete a department with active employees.")

    def perform_destroy(self, instance):
        # DEP-05 + financial-integrity spirit: soft-delete, never hard-remove.
        self._guard_active_employees(instance)
        instance.is_active = False
        instance.save(update_fields=["is_active", "updated_at"])

    @action(detail=True, methods=["post"])
    def activate(self, request, pk=None):
        dept = self.get_object()
        dept.is_active = True
        dept.save(update_fields=["is_active", "updated_at"])
        return Response(self.get_serializer(dept).data)

    @action(detail=True, methods=["post"])
    def deactivate(self, request, pk=None):
        dept = self.get_object()
        self._guard_active_employees(dept)
        dept.is_active = False
        dept.save(update_fields=["is_active", "updated_at"])
        return Response(self.get_serializer(dept).data, status=status.HTTP_200_OK)


class EmployeeViewSet(viewsets.ModelViewSet):
    """Employee master CRUD (EMP-01/02). Tenant-isolated by schema (RULE #1)."""

    serializer_class = EmployeeSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["employee_code", "first_name", "last_name", "work_email"]
    ordering_fields = ["employee_code", "last_name", "created_at"]

    def get_queryset(self):
        qs = Employee.objects.select_related("department")
        params = self.request.query_params
        is_active = params.get("is_active")
        if is_active is not None:
            qs = qs.filter(is_active=is_active.lower() in ("1", "true", "yes"))
        department = params.get("department")
        if department is not None:
            qs = qs.filter(department_id=department)
        return qs

    def perform_destroy(self, instance):
        # Master data: soft-delete (deactivate), never hard-remove.
        instance.is_active = False
        instance.save(update_fields=["is_active", "updated_at"])

    @action(detail=True, methods=["post"])
    def activate(self, request, pk=None):
        emp = self.get_object()
        emp.is_active = True
        emp.save(update_fields=["is_active", "updated_at"])
        return Response(self.get_serializer(emp).data)

    @action(detail=True, methods=["post"])
    def deactivate(self, request, pk=None):
        emp = self.get_object()
        emp.is_active = False
        emp.save(update_fields=["is_active", "updated_at"])
        return Response(self.get_serializer(emp).data)
