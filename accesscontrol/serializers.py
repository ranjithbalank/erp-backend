from rest_framework import serializers

from .models import Department


class DepartmentSerializer(serializers.ModelSerializer):
    """Explicit allowlist of fields (never `__all__`, per CLAUDE.md §6)."""

    class Meta:
        model = Department
        fields = [
            "id",
            "code",
            "name",
            "description",
            "parent",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

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
