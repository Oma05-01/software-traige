from django.urls import path

from .views import health_check, liveness_check
from .dashboard_views import DashboardOverviewView


urlpatterns = [
    path(
        "health/live/",
        liveness_check,
        name="health-live",
    ),
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
