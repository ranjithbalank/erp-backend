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


class Employee(models.Model):
    """An employee within a tenant (MOD-SEC-001, EMP-01/02).

    Tenant-isolated by schema (RULE #1). An Employee is an HR record and may
    exist WITHOUT a system user (EMP-06); linking to a User account is the
    separate provisioning step (EMP-03/04).
    """

    class EmploymentType(models.TextChoices):
        FULL_TIME = "full_time", "Full-time"
        PART_TIME = "part_time", "Part-time"
        CONTRACT = "contract", "Contract"
        INTERN = "intern", "Intern"

    employee_code = models.CharField(
        max_length=30,
        unique=True,
        validators=[department_code_validator],
        help_text="Unique per tenant, e.g. EMP-00123.",
    )
    first_name = models.CharField(max_length=60)
    last_name = models.CharField(max_length=60)
    # Optional, but unique per tenant when present (EMP edge case: no work email).
    work_email = models.EmailField(null=True, blank=True, unique=True)
    phone = models.CharField(max_length=30, blank=True, default="")
    designation = models.CharField(max_length=100)  # EMP-02
    department = models.ForeignKey(  # EMP-02
        "accesscontrol.Department",
        on_delete=models.PROTECT,
        related_name="employees",
    )
    employment_type = models.CharField(
        max_length=20,
        choices=EmploymentType.choices,
        default=EmploymentType.FULL_TIME,
    )
    date_of_joining = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["employee_code"]
        verbose_name = "employee"
        verbose_name_plural = "employees"

    def __str__(self) -> str:
        return f"{self.employee_code} — {self.full_name}"

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    def save(self, *args, **kwargs):
        if self.employee_code:
            self.employee_code = self.employee_code.strip().upper()
        # Store blank email as NULL so the unique constraint allows many "no email".
        if not self.work_email:
            self.work_email = None
        super().save(*args, **kwargs)
