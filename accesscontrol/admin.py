from django.contrib import admin

from .models import Department, Employee


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "parent", "is_active", "updated_at")
    list_filter = ("is_active",)
    search_fields = ("code", "name")


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = (
        "employee_code",
        "full_name",
        "designation",
        "department",
        "employment_type",
        "is_active",
    )
    list_filter = ("is_active", "employment_type", "department")
    search_fields = ("employee_code", "first_name", "last_name", "work_email")
