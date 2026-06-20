from django.contrib import admin

from .models import Department, Employee, Role, UserProfile


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


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ("name", "role_type", "is_system", "is_active")
    list_filter = ("role_type", "is_system", "is_active")
    search_fields = ("name",)


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "employee", "status")
    list_filter = ("status",)
    search_fields = ("user__username", "user__email")
