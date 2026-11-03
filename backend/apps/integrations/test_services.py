from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from apps.agents.models import AgentExecution
from apps.agents.services import (
    complete_agent_execution,
    create_agent_execution,
    start_agent_execution,
)
from apps.integrations.models import ActionExecution
from apps.integrations.services import (
    ActionNotAuthorized,
    ActionExecutionNotReady,
    create_action_execution,
    execute_action_execution,
)
from apps.reviews.models import ReviewRequest
from apps.tickets.models import Ticket
from apps.workflow.models import WorkflowRun
from apps.workflow.services import (
    create_workflow_for_ticket,
    transition_workflow,
)


User = get_user_model()


class ActionExecutionTests(TestCase):

    def setUp(self):
        self.reviewer = User.objects.create_user(
            username="action-reviewer",
            password="test-password",
            is_staff=True,
        )

        self.ticket = Ticket.objects.create(
            title="PDF upload failure",
            description="The application crashes during PDF upload.",
            reporter_name="Test Reporter",
            reporter_email="reporter@example.com",
            environment="Windows 11, Chrome",
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

        self.agent_execution = create_agent_execution(
            self.workflow.id,
            AgentExecution.AgentType.SUPPORT_REP,
            {"ticket_id": str(self.ticket.id)},
        )

        self.agent_execution, _ = start_agent_execution(
            self.agent_execution.id,
        )

        complete_agent_execution(
            self.agent_execution.id,
            self.support_response_payload(),
        )

        self.review = ReviewRequest.objects.create(
            workflow_run=self.workflow,
            agent_execution=self.agent_execution,
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
            "subject": "Update on your PDF upload report",
            "draft_response": (
                "Thank you for reporting this issue. "
                "We have received your report."
            ),
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

    def approve_review(self):
        self.review.status = ReviewRequest.Status.APPROVED
        self.review.reviewed_by = self.reviewer
        self.review.reviewed_at = timezone.now()

        self.review.save(
            update_fields=[
                "status",
                "reviewed_by",
                "reviewed_at",
            ],
        )

    def test_pending_review_cannot_create_action_execution(self):
        with self.assertRaises(ActionNotAuthorized):
            create_action_execution(self.review.id)

        self.assertFalse(
            ActionExecution.objects.filter(
                review_request=self.review,
            ).exists()
        )

    def test_approved_review_creates_queued_execution(self):
        self.approve_review()

        execution = create_action_execution(
            self.review.id,
        )

        self.assertEqual(
            execution.status,
            ActionExecution.Status.QUEUED,
        )

        self.assertEqual(execution.attempt_count, 0)

        self.assertEqual(
            execution.request_payload["recipient"],
            self.ticket.reporter_email,
        )

        self.assertEqual(
            execution.request_payload["subject"],
            self.review.proposed_payload["subject"],
        )

        self.assertTrue(execution.idempotency_key)

    def test_action_execution_creation_is_idempotent(self):
        self.approve_review()

        first = create_action_execution(self.review.id)
        second = create_action_execution(self.review.id)

        self.assertEqual(first.id, second.id)

        self.assertEqual(
            ActionExecution.objects.filter(
                review_request=self.review,
            ).count(),
            1,
        )

    def test_rejected_review_cannot_create_action_execution(self):
        self.review.status = ReviewRequest.Status.REJECTED
        self.review.reviewed_by = self.reviewer
        self.review.reviewed_at = timezone.now()

        self.review.save(
            update_fields=[
                "status",
                "reviewed_by",
                "reviewed_at",
            ],
        )

        with self.assertRaises(ActionNotAuthorized):
            create_action_execution(self.review.id)

    def test_mock_execution_succeeds_without_external_delivery(self):
        self.approve_review()

        execution = create_action_execution(
            self.review.id,
        )

        completed = execute_action_execution(execution.id)

        self.assertEqual(
            completed.status,
            ActionExecution.Status.SUCCEEDED,
        )

        self.assertEqual(completed.attempt_count, 1)

        self.assertTrue(
            completed.provider_response["accepted"]
        )

        self.assertEqual(
            completed.provider_response["delivery_mode"],
            "mock",
        )

        self.assertFalse(
            completed.provider_response["external_delivery_performed"]
        )

        self.assertIn(
            "No external email was sent",
            completed.provider_response["note"],
        )

    def test_duplicate_execution_does_not_call_provider_twice(self):
        self.approve_review()

        execution = create_action_execution(self.review.id)

        class CountingProvider:
            def __init__(self):
                self.calls = 0

            def send(self, **kwargs):
                self.calls += 1

                return {
                    "provider": "mock_email",
                    "delivery_mode": "mock",
                    "accepted": True,
                    "external_delivery_performed": False,
                }

        provider = CountingProvider()

        first = execute_action_execution(
            execution.id,
            provider=provider,
        )

        second = execute_action_execution(
            execution.id,
            provider=provider,
        )

        self.assertEqual(first.id, second.id)
        self.assertEqual(provider.calls, 1)
        self.assertEqual(second.attempt_count, 1)

    def test_provider_failure_is_recorded(self):
        self.approve_review()

        execution = create_action_execution(
            self.review.id,
        )

        class FailingProvider:
            def send(self, **kwargs):
                raise RuntimeError("Simulated provider failure")

        with self.assertRaises(RuntimeError):
            execute_action_execution(
                execution.id,
                provider=FailingProvider(),
            )

        execution.refresh_from_db()

        self.assertEqual(
            execution.status,
            ActionExecution.Status.FAILED,
        )

        self.assertEqual(
            execution.error_code,
            "RuntimeError",
        )

        self.assertIsNotNone(execution.finished_at)

    def test_failed_action_is_not_silently_retried(self):
        self.approve_review()

        execution = create_action_execution(
            self.review.id,
        )

        class FailingProvider:
            def send(self, **kwargs):
                raise RuntimeError("Provider unavailable")

        with self.assertRaises(RuntimeError):
            execute_action_execution(
                execution.id,
                provider=FailingProvider(),
            )

        with self.assertRaises(ActionExecutionNotReady):
            execute_action_execution(execution.id)