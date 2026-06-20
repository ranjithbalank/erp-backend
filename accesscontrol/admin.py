from django.contrib import admin

from .models import Department


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "parent", "is_active", "updated_at")
    list_filter = ("is_active",)
    search_fields = ("code", "name")
