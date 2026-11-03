from django.urls import path

from .views import health_check
from .dashboard_views import DashboardOverviewView

urlpatterns = [
    path(
        "health/",
        health_check,
        name="health-check",
    ),
    path(
        "dashboard/",
        DashboardOverviewView.as_view(),
        name="dashboard-overview",
    ),
]