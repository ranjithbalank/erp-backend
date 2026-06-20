from django.db import models
from django_tenants.models import DomainMixin, TenantMixin


class Client(TenantMixin):
    """A tenant. Each Client owns an isolated PostgreSQL schema.

    The platform (public) schema stores the registry of tenants; all
    tenant business data lives inside the tenant's own schema (RULE #1).
    """

    name = models.CharField(max_length=100)
    created_on = models.DateField(auto_now_add=True)

    # Create/drop the tenant's schema automatically on save/delete.
    auto_create_schema = True
    auto_drop_schema = True

    def __str__(self) -> str:
        return f"{self.name} ({self.schema_name})"


class Domain(DomainMixin):
    """Maps a hostname to a tenant. The request host selects the schema."""

    def __str__(self) -> str:
        return self.domain
