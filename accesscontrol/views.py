from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Department
from .serializers import DepartmentSerializer


class DepartmentViewSet(viewsets.ModelViewSet):
    """Department master CRUD (DEP-01/02/03).

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
        qs = Department.objects.all()
        is_active = self.request.query_params.get("is_active")
        if is_active is not None:
            qs = qs.filter(is_active=is_active.lower() in ("1", "true", "yes"))
        return qs

    def perform_destroy(self, instance):
        # DEP-05 / financial-integrity spirit: master data is soft-deleted
        # (deactivated), never hard-removed.
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
        dept.is_active = False
        dept.save(update_fields=["is_active", "updated_at"])
        return Response(self.get_serializer(dept).data, status=status.HTTP_200_OK)
