from rest_framework.routers import DefaultRouter

from .views import DepartmentViewSet, EmployeeViewSet

router = DefaultRouter()
router.register(r"departments", DepartmentViewSet, basename="department")
router.register(r"employees", EmployeeViewSet, basename="employee")

urlpatterns = router.urls
