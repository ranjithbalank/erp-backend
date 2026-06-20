from rest_framework.routers import DefaultRouter

from .views import (
    DepartmentViewSet,
    EmployeeViewSet,
    RoleViewSet,
    UserProfileViewSet,
)

router = DefaultRouter()
router.register(r"departments", DepartmentViewSet, basename="department")
router.register(r"employees", EmployeeViewSet, basename="employee")
router.register(r"roles", RoleViewSet, basename="role")
router.register(r"users", UserProfileViewSet, basename="userprofile")

urlpatterns = router.urls
