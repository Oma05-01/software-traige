from django.db.models import Count, Q

from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView
from apps.reviews.models import ReviewRequest
from apps.tickets.models import Ticket
from apps.workflow.models import WorkflowRun
from apps.events.models import WorkflowEvent


class DashboardOverviewView(APIView):
    """
    Staff-only dashboard statistics and recent workflow activity.
    """

    permission_classes = [IsAdminUser]

    def get(self, request):
        ticket_counts = Ticket.objects.aggregate(
            total_tickets=Count("id"),
            in_progress_tickets=Count(
                "id",
                filter=Q(status=Ticket.Status.IN_PROGRESS),
            ),
            awaiting_review_tickets=Count(
                "id",
                filter=Q(status=Ticket.Status.AWAITING_REVIEW),
            ),
            completed_tickets=Count(
                "id",
                filter=Q(
                    status__in=[
                        Ticket.Status.COMPLETED,
                        Ticket.Status.CLOSED,
                    ]
                ),
            ),
        )

        workflow_counts = WorkflowRun.objects.aggregate(
            active_workflows=Count(
                "id",
                filter=Q(
                    status__in=[
                        WorkflowRun.Status.QUEUED,
                        WorkflowRun.Status.RUNNING,
                    ]
                ),
            ),
            failed_workflows=Count(
                "id",
                filter=Q(status=WorkflowRun.Status.FAILED),
            ),
        )

        pending_review_requests = ReviewRequest.objects.filter(
            status=ReviewRequest.Status.PENDING
        ).count()

        recent_events = (
            WorkflowEvent.objects
            .select_related("workflow_run__ticket")
            .order_by("-created_at", "-id")[:10]
        )

        activity = [
            {
                "id": str(event.id),
                "event_type": event.event_type,
                "source": event.source,
                "created_at": event.created_at,
                "workflow_id": str(event.workflow_run_id),
                "ticket_id": str(event.workflow_run.ticket_id),
                "ticket_title": event.workflow_run.ticket.title,
            }
            for event in recent_events
        ]

        return Response({
            "statistics": {
                **ticket_counts,
                **workflow_counts,
                "pending_review_requests": pending_review_requests,
            },
            "recent_activity": activity,
        })