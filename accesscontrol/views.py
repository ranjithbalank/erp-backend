from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import Count, Q
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Department, Employee, Role, UserProfile
from .serializers import (
    DepartmentSerializer,
    EmployeeSerializer,
    ProvisionUserSerializer,
    RoleSerializer,
    UserProfileSerializer,
)


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

    @staticmethod
    def _disable_linked_user(emp):
        # EMP-07: deactivating an employee revokes their system access.
        profile = getattr(emp, "user_profile", None)
        if profile is not None:
            profile.status = UserProfile.Status.DEACTIVATED
            profile.save(update_fields=["status", "updated_at"])
            profile.user.is_active = False
            profile.user.save(update_fields=["is_active"])

    def perform_destroy(self, instance):
        # Master data: soft-delete (deactivate), never hard-remove.
        instance.is_active = False
        instance.save(update_fields=["is_active", "updated_at"])
        self._disable_linked_user(instance)

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
        self._disable_linked_user(emp)  # EMP-07
        return Response(self.get_serializer(emp).data)

    @action(detail=True, methods=["post"], url_path="provision-user")
    def provision_user(self, request, pk=None):
        """Provision a system user from this employee (EMP-03/04, USR-01/02/03)."""
        emp = self.get_object()
        if getattr(emp, "user_profile", None) is not None:
            raise ValidationError("This employee already has a linked user.")

        data = ProvisionUserSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        v = data.validated_data

        email = (v.get("email") or emp.work_email or "").strip()
        username = (v.get("username") or "").strip() or (
            email.split("@")[0] if email else emp.employee_code.lower()
        )

        # USR-03: unique email/username within the tenant (schema-scoped).
        if username and User.objects.filter(username=username).exists():
            raise ValidationError({"username": "Username already exists."})
        if email and User.objects.filter(email__iexact=email).exists():
            raise ValidationError({"email": "Email already in use."})

        with transaction.atomic():
            user = User.objects.create_user(
                username=username, email=email or "", password=v["password"]
            )
            profile = UserProfile.objects.create(
                user=user, employee=emp, status=UserProfile.Status.INVITED
            )
            profile.roles.set(Role.objects.filter(id__in=v["role_ids"]))

        out = UserProfileSerializer(profile)
        return Response(out.data, status=status.HTTP_201_CREATED)


class RoleViewSet(viewsets.ModelViewSet):
    """Role master CRUD (ROL-01/02/03/06/07). Tenant-isolated by schema."""

    serializer_class = RoleSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name", "description"]
    ordering_fields = ["name", "created_at"]

    def get_queryset(self):
        qs = Role.objects.annotate(user_count=Count("users"))  # ROL-07
        is_active = self.request.query_params.get("is_active")
        if is_active is not None:
            qs = qs.filter(is_active=is_active.lower() in ("1", "true", "yes"))
        return qs

    def perform_update(self, serializer):
        if serializer.instance.is_system:  # ROL-03
            raise ValidationError("System roles cannot be edited (clone instead).")
        serializer.save()

    def perform_destroy(self, instance):
        if instance.is_system:  # ROL-03
            raise ValidationError("System roles cannot be deleted.")
        if instance.users.exists():  # ROL-06
            raise ValidationError("Reassign users before deleting this role.")
        instance.delete()

    @action(detail=True, methods=["post"])
    def clone(self, request, pk=None):
        """ROL-03: clone a (system or custom) role into a new custom role."""
        src = self.get_object()
        name = (request.data.get("name") or f"{src.name} (copy)").strip()
        if Role.objects.filter(name=name).exists():
            raise ValidationError({"name": "A role with this name already exists."})
        clone = Role.objects.create(
            name=name,
            role_type=Role.RoleType.CUSTOM,
            description=src.description,
            is_system=False,
        )
        return Response(self.get_serializer(clone).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def activate(self, request, pk=None):
        role = self.get_object()
        role.is_active = True
        role.save(update_fields=["is_active", "updated_at"])
        return Response(self.get_serializer(role).data)

    @action(detail=True, methods=["post"])
    def deactivate(self, request, pk=None):
        role = self.get_object()
        role.is_active = False
        role.save(update_fields=["is_active", "updated_at"])
        return Response(self.get_serializer(role).data)


class UserProfileViewSet(viewsets.ReadOnlyModelViewSet):
    """Provisioned users: list/retrieve + role assignment (USR-01/02)."""

    serializer_class = UserProfileSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter]
    search_fields = ["user__username", "user__email"]

    def get_queryset(self):
        return UserProfile.objects.select_related("user", "employee").prefetch_related("roles")

    @action(detail=True, methods=["post"], url_path="set-roles")
    def set_roles(self, request, pk=None):
        """USR-02: replace a user's role set (at least one role required)."""
        profile = self.get_object()
        role_ids = request.data.get("role_ids")
        if not isinstance(role_ids, list) or not role_ids:
            raise ValidationError({"role_ids": "Provide at least one role id."})
        roles = Role.objects.filter(id__in=role_ids, is_active=True)
        if roles.count() != len(set(role_ids)):
            raise ValidationError({"role_ids": "One or more roles are invalid."})
        profile.roles.set(roles)
        return Response(self.get_serializer(profile).data)
