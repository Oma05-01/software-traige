from django.urls import path

from apps.workflow.api_views import TicketWorkflowDetailView
from apps.workflow.office_views import OfficeActivityView

urlpatterns = [
    path(
        "tickets/<uuid:ticket_id>/",
        TicketWorkflowDetailView.as_view(),
        name="ticket-workflow-detail",
    ),
    path(
        "office/",
        OfficeActivityView.as_view(),
        name="office-activity",
    ),
]
