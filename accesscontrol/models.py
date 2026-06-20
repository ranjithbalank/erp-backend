from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models

# Code like "DEP-FIN": letters/digits with hyphen/underscore. Input may be any
# case; it is normalised to uppercase on save (so it is unique case-insensitively).
department_code_validator = RegexValidator(
    regex=r"^[A-Za-z0-9][A-Za-z0-9_-]{1,29}$",
    message="Code must be 2-30 chars: letters/digits with '-' or '_'.",
)


class Department(models.Model):
    """A department within a tenant (MOD-SEC-001, DEP-01..03).

    Tenant isolation is enforced by the schema: this table lives inside each
    tenant's own PostgreSQL schema, so `unique=True` is unique *per tenant*
    (RULE #1). There is deliberately no tenant FK to leak across.
    """

    code = models.CharField(
        max_length=30,
        unique=True,
        validators=[department_code_validator],
        help_text="Unique per tenant, e.g. DEP-FIN.",
    )
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, default="")
    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="children",
        help_text="Optional parent for sub-departments (DEP-03).",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "department"
        verbose_name_plural = "departments"

    def __str__(self) -> str:
        return f"{self.code} — {self.name}"

    def clean(self):
        # Normalise code so uniqueness is predictable.
        if self.code:
            self.code = self.code.strip().upper()
        # A department cannot be its own parent, nor part of a cycle.
        if self.parent_id and self.parent_id == self.id:
            raise ValidationError({"parent": "A department cannot be its own parent."})
        ancestor = self.parent
        while ancestor is not None:
            if ancestor.id == self.id:
                raise ValidationError({"parent": "Circular parent relationship."})
            ancestor = ancestor.parent

    def save(self, *args, **kwargs):
        # Normalise code on every write path (API, admin, shell). Field/format
        # and parent-cycle validation live in the serializer (DRF 400s) and in
        # clean() (admin).
        if self.code:
            self.code = self.code.strip().upper()
        super().save(*args, **kwargs)
