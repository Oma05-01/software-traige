
from collections import defaultdict

from django.utils import timezone

from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.agents.models import AgentExecution


AGENT_TYPES = (
    AgentExecution.AgentType.RECEPTIONIST,
    AgentExecution.AgentType.DEBUGGER,
    AgentExecution.AgentType.PRODUCT_MANAGER,
    AgentExecution.AgentType.SUPPORT_REP,
)

ACTIVE_STATUSES = (
    AgentExecution.Status.QUEUED,
    AgentExecution.Status.RUNNING,
)


def serialize_execution(execution):
    if execution is None:
        return None

    workflow = execution.workflow_run
    ticket = workflow.ticket

    return {
        "id": str(execution.id),
        "agent_type": execution.agent_type,
        "status": execution.status,
        "attempt": execution.attempt,
        "ticket_id": str(ticket.id),
        "ticket_title": ticket.title,
        "workflow_id": str(workflow.id),
        "workflow_status": workflow.status,
        "workflow_stage": workflow.current_stage,
        "started_at": execution.started_at,
        "finished_at": execution.finished_at,
        "created_at": execution.created_at,
        "updated_at": execution.updated_at,
        "error_code": execution.error_code,
    }


def get_display_status(current, latest):
    if current is not None:
        if current.status == AgentExecution.Status.RUNNING:
            return "working"

        return "queued"

    if latest is None:
        return "idle"

    if latest.status == AgentExecution.Status.SUCCEEDED:
        return "completed"

    if latest.status == AgentExecution.Status.FAILED:
        return "failed"

    return "idle"


class OfficeActivityView(APIView):
    """
    Returns the latest activity for the four virtual office agents.

    Access is restricted to authenticated staff members.
    """

    permission_classes = [IsAdminUser]

    def get(self, request):
        queryset = (
            AgentExecution.objects
            .select_related(
                "workflow_run",
                "workflow_run__ticket",
            )
        )

        active_executions = list(
            queryset
            .filter(status__in=ACTIVE_STATUSES)
            .order_by("-created_at")
        )

        active_by_agent = defaultdict(list)

        for execution in active_executions:
            active_by_agent[execution.agent_type].append(execution)

        agents = []

        for agent_type in AGENT_TYPES:
            active = active_by_agent[agent_type]

            running = next(
                (
                    execution
                    for execution in active
                    if execution.status == AgentExecution.Status.RUNNING
                ),
                None,
            )

            queued = next(
                (
                    execution
                    for execution in active
                    if execution.status == AgentExecution.Status.QUEUED
                ),
                None,
            )

            current = running or queued

            latest = (
                queryset
                .filter(agent_type=agent_type)
                .order_by("-created_at", "-attempt")
                .first()
            )

            agents.append({
                "agent_type": agent_type,
                "status": get_display_status(current, latest),
                "active_count": len(active),
                "current_execution": serialize_execution(current),
                "latest_execution": serialize_execution(latest),
            })

        recent_executions = (
            queryset
            .order_by("-created_at", "-attempt")[:12]
        )

        return Response({
            "agents": agents,
            "recent_executions": [
                serialize_execution(execution)
                for execution in recent_executions
            ],
            "updated_at": timezone.now(),
        })
