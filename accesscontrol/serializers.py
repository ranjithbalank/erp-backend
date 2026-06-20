from django.contrib.auth.models import User
from rest_framework import serializers

from .models import Department, Employee, Role, UserProfile


class DepartmentSerializer(serializers.ModelSerializer):
    """Explicit allowlist of fields (never `__all__`, per CLAUDE.md §6)."""

    # DEP-06: number of active employees in this department (read-only).
    employee_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Department
        fields = [
            "id",
            "code",
            "name",
            "description",
            "parent",
            "is_active",
            "employee_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "employee_count", "created_at", "updated_at"]

    def validate_code(self, value: str) -> str:
        return value.strip().upper()

    def validate(self, attrs):
        parent = attrs.get("parent")
        if parent is not None:
            instance = self.instance
            # No self-parent and no cycle (DEP-03 integrity).
            ancestor = parent
            while ancestor is not None:
                if instance is not None and ancestor.pk == instance.pk:
                    raise serializers.ValidationError(
                        {"parent": "A department cannot be its own parent or a cycle."}
                    )
                ancestor = ancestor.parent
        return attrs


class EmployeeSerializer(serializers.ModelSerializer):
    """Explicit allowlist (EMP-01/02). `department` is required (EMP-02)."""

    full_name = serializers.CharField(read_only=True)

    class Meta:
        model = Employee
        fields = [
            "id",
            "employee_code",
            "first_name",
            "last_name",
            "full_name",
            "work_email",
            "phone",
            "designation",
            "department",
            "employment_type",
            "date_of_joining",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "full_name", "created_at", "updated_at"]


class RoleSerializer(serializers.ModelSerializer):
    """ROL-01/02. `is_system`/`role_type` are server-controlled (ROL-03)."""

    user_count = serializers.IntegerField(read_only=True)  # ROL-07

    class Meta:
        model = Role
        fields = [
            "id",
            "name",
            "role_type",
            "description",
            "is_system",
            "is_active",
            "user_count",
            "created_at",
            "updated_at",
        ]
        # Roles created via the API are always custom; system flag is set only
        # by the seed migration (ROL-03).
        read_only_fields = [
            "id",
            "role_type",
            "is_system",
            "user_count",
            "created_at",
            "updated_at",
        ]


class _UserSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "email", "is_active"]


class UserProfileSerializer(serializers.ModelSerializer):
    """Read view of a provisioned user (USR-01/02/04)."""

    user = _UserSummarySerializer(read_only=True)
    roles = RoleSerializer(many=True, read_only=True)

    class Meta:
        model = UserProfile
        fields = ["id", "user", "employee", "status", "roles", "created_at", "updated_at"]
        read_only_fields = fields


class ProvisionUserSerializer(serializers.Serializer):
    """Input for provisioning a user from an employee (EMP-03/04, USR-01/02/03)."""

    username = serializers.CharField(required=False, allow_blank=True)
    email = serializers.EmailField(required=False, allow_blank=True)
    password = serializers.CharField(write_only=True, min_length=14)  # CLAUDE.md §7
    role_ids = serializers.ListField(
        child=serializers.IntegerField(), allow_empty=False  # EMP-04: >= 1 role
    )

    def validate_role_ids(self, value):
        roles = Role.objects.filter(id__in=value, is_active=True)
        if roles.count() != len(set(value)):
            raise serializers.ValidationError("One or more roles are invalid or inactive.")
        return value

    def validate_employee_code(self, value: str) -> str:
        return value.strip().upper()
