from rest_framework import serializers

from .models import Department, Employee


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

    def validate_employee_code(self, value: str) -> str:
        return value.strip().upper()
