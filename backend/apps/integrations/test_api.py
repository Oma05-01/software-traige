from django.contrib.auth import get_user_model
from django.urls import reverse

from rest_framework import status
from rest_framework.test import APITestCase

from apps.agents.models import AgentExecution
from apps.agents.services import (
    complete_agent_execution,
    create_agent_execution,
    start_agent_execution,
)
from apps.integrations.models import ActionExecution
from apps.reviews.models import ReviewRequest
from apps.tickets.models import Ticket
from apps.workflow.models import WorkflowRun
from apps.workflow.services import (
    create_workflow_for_ticket,
    transition_workflow,
)


User = get_user_model()


class ActionExecutionAPITests(APITestCase):

    def setUp(self):
        self.ticket = Ticket.objects.create(
            title="PDF upload failure",
            description="The application crashes during PDF upload.",
            reporter_name="Test Reporter",
            reporter_email="reporter@example.com",
            category=Ticket.Category.BUG,
            priority=Ticket.Priority.HIGH,
        )

        self.workflow = create_workflow_for_ticket(
            self.ticket.id,
        )

        transition_workflow(
            self.workflow.id,
            WorkflowRun.Status.RUNNING,
        )

        execution = create_agent_execution(
            self.workflow.id,
            AgentExecution.AgentType.SUPPORT_REP,
            {"ticket_id": str(self.ticket.id)},
        )

        execution, _ = start_agent_execution(execution.id)

        complete_agent_execution(
            execution.id,
            self.support_response_payload(),
        )

        self.staff_user = User.objects.create_user(
            username="integration-reviewer",
            password="test-password",
            is_staff=True,
        )

        self.review = ReviewRequest.objects.create(
            workflow_run=self.workflow,
            agent_execution=execution,
            action_type=(
                ReviewRequest.ActionType.SEND_SUPPORT_RESPONSE
            ),
            status=ReviewRequest.Status.PENDING,
            proposed_payload=self.support_response_payload(),
        )

    @staticmethod
    def support_response_payload():
        return {
            "draft_status": "pending_human_review",
            "subject": "Update on your report",
            "draft_response": "Thank you for reporting this issue.",
            "response_type": "acknowledgement",
            "follow_up_questions": [],
            "evidence_references": [],
            "internal_review_notes": [],
            "requires_human_review": True,
            "external_send_authorized": False,
            "responder": {
                "name": "deterministic_support_rep",
                "version": "1.0.0",
            },
        }

    def test_anonymous_user_cannot_queue_action(self):
        url = reverse(
            "integrations:queue-approved-action",
            kwargs={"review_id": self.review.id},
        )

        response = self.client.post(url)

        self.assertIn(
            response.status_code,
            [
                status.HTTP_401_UNAUTHORIZED,
                status.HTTP_403_FORBIDDEN,
            ],
        )

    def test_unapproved_review_cannot_be_executed(self):
        self.client.force_authenticate(
            user=self.staff_user,
        )

        url = reverse(
            "integrations:queue-approved-action",
            kwargs={"review_id": self.review.id},
        )

        response = self.client.post(url)

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        self.assertFalse(
            ActionExecution.objects.filter(
                review_request=self.review,
            ).exists()
        )

    def test_approved_review_can_be_queued(self):
        from django.utils import timezone

        self.review.status = ReviewRequest.Status.APPROVED
        self.review.reviewed_by = self.staff_user
        self.review.reviewed_at = timezone.now()

        self.review.save(
            update_fields=[
                "status",
                "reviewed_by",
                "reviewed_at",
            ],
        )

        self.client.force_authenticate(
            user=self.staff_user,
        )

        url = reverse(
            "integrations:queue-approved-action",
            kwargs={"review_id": self.review.id},
        )

        response = self.client.post(url)

        self.assertEqual(
            response.status_code,
            status.HTTP_202_ACCEPTED,
        )

        self.assertEqual(
            response.data["status"],
            ActionExecution.Status.QUEUED,
        )

    def test_staff_can_inspect_action_execution(self):
        from django.utils import timezone

        self.review.status = ReviewRequest.Status.APPROVED
        self.review.reviewed_by = self.staff_user
        self.review.reviewed_at = timezone.now()

        self.review.save(
            update_fields=[
                "status",
                "reviewed_by",
                "reviewed_at",
            ],
        )

        self.client.force_authenticate(
            user=self.staff_user,
        )

        queue_url = reverse(
            "integrations:queue-approved-action",
            kwargs={"review_id": self.review.id},
        )

        queued = self.client.post(queue_url)

        action_id = queued.data["id"]

        detail_url = reverse(
            "integrations:action-execution-detail",
            kwargs={"pk": action_id},
        )

        response = self.client.get(detail_url)

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertNotIn(
            "request_payload",
            response.data,
        )