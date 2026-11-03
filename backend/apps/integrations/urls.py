from django.urls import path

from apps.integrations.views import (
    ActionExecutionDetailView,
    QueueApprovedActionView,
)


app_name = "integrations"

urlpatterns = [
    path(
        "reviews/<uuid:review_id>/execute/",
        QueueApprovedActionView.as_view(),
        name="queue-approved-action",
    ),
    path(
        "actions/<uuid:pk>/",
        ActionExecutionDetailView.as_view(),
        name="action-execution-detail",
    ),
]