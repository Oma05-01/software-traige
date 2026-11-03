from rest_framework import generics
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAdminUser

from apps.workflow.models import WorkflowRun
from apps.workflow.api_serializers import WorkflowReadSerializer


class TicketWorkflowDetailView(generics.RetrieveAPIView):

    serializer_class = WorkflowReadSerializer
    permission_classes = [IsAdminUser]

    def get_queryset(self):
        return (
            WorkflowRun.objects
            .select_related("ticket")
            .prefetch_related(
                "agent_executions",
                "events",
            )
        )

    def get_object(self):
        workflow = (
            self.get_queryset()
            .filter(
                ticket_id=self.kwargs["ticket_id"]
            )
            .order_by("-created_at")
            .first()
        )

        if workflow is None:
            raise NotFound(
                "No workflow was found for this ticket."
            )

        self.check_object_permissions(
            self.request,
            workflow,
        )

        return workflow