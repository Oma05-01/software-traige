from unittest.mock import patch

from django.test import TestCase

from apps.tickets.models import Ticket
from django.test import override_settings
from apps.workflow.models import WorkflowRun
from apps.workflow.services import (
    create_workflow_for_ticket,
    transition_workflow,
)
from apps.events.models import WorkflowEvent
from apps.agents.llm.base import LLMTransientError
from apps.agents.services import (
    create_agent_execution,
    start_agent_execution,
)
from .models import AgentExecution
from .runner import run_receptionist
from apps.reviews.models import ClassificationReview

@override_settings(RECEPTIONIST_MODE="deterministic")
class ReceptionistRunnerTests(TestCase):

    def setUp(self):
        self.ticket = Ticket.objects.create(
            title="PDF upload failure",
            description=(
                "The application crashes when uploading "
                "PDF files larger than 25 MB."
            ),
            reporter_email="reporter@example.com",
            environment="Windows 11, Chrome",
        )

        self.workflow = create_workflow_for_ticket(
            self.ticket.id
        )

        self.workflow = transition_workflow(
            self.workflow.id,
            WorkflowRun.Status.RUNNING,
        )

        self.ticket.refresh_from_db()

        self.assertEqual(
            self.ticket.status,
            Ticket.Status.IN_PROGRESS,
        )

    def test_receptionist_executes_and_classifies_bug(self):

        execution = run_receptionist(self.workflow.id)

        self.ticket.refresh_from_db()
        self.workflow.refresh_from_db()

        self.assertEqual(
            execution.status,
            AgentExecution.Status.SUCCEEDED,
        )

        self.assertEqual(
            self.ticket.category,
            Ticket.Category.BUG,
        )

        self.assertEqual(
            self.ticket.priority,
            Ticket.Priority.HIGH,
        )

        self.assertEqual(
            self.workflow.current_stage,
            WorkflowRun.Stage.DEBUGGER,
        )

        self.assertEqual(
            self.workflow.status,
            WorkflowRun.Status.RUNNING,
        )

    def test_feature_request_routes_to_product_manager(self):

        self.ticket.title = "CSV export support"
        self.ticket.description = (
            "Please add support for CSV exports."
        )

        self.ticket.save()

        execution = run_receptionist(self.workflow.id)

        self.ticket.refresh_from_db()
        self.workflow.refresh_from_db()

        self.assertEqual(
            execution.status,
            AgentExecution.Status.SUCCEEDED,
        )

        self.assertEqual(
            self.ticket.category,
            Ticket.Category.FEATURE,
        )

        self.assertEqual(
            self.workflow.current_stage,
            WorkflowRun.Stage.PRODUCT_MANAGER,
        )

    def test_unclear_report_requires_human_review(self):

        self.ticket.title = "Application question"
        self.ticket.description = (
            "I would like some information."
        )

        self.ticket.save()

        execution = run_receptionist(self.workflow.id)

        self.ticket.refresh_from_db()
        self.workflow.refresh_from_db()

        self.assertEqual(
            execution.status,
            AgentExecution.Status.SUCCEEDED,
        )

        self.assertEqual(
            self.workflow.status,
            WorkflowRun.Status.AWAITING_REVIEW,
        )

        self.assertEqual(
            self.workflow.current_stage,
            WorkflowRun.Stage.HUMAN_REVIEW,
        )

        self.assertEqual(
            self.ticket.status,
            Ticket.Status.AWAITING_REVIEW,
        )

        review = ClassificationReview.objects.get(
            workflow_run=self.workflow,
        )

        self.assertEqual(
            review.agent_execution,
            execution,
        )

        self.assertEqual(
            review.proposed_category,
            execution.output_payload["category"],
        )

        self.assertEqual(
            review.proposed_priority,
            execution.output_payload["priority"],
        )

        self.assertEqual(
            review.status,
            ClassificationReview.Status.PENDING,
        )

        # The agent's uncertain suggestion must not become
        # the ticket's confirmed classification.
        self.assertEqual(
            self.ticket.category,
            Ticket.Category.UNCLASSIFIED,
        )

        self.assertEqual(
            self.ticket.priority,
            Ticket.Priority.UNASSESSED,
        )

    def test_repeated_invocation_does_not_duplicate_execution(self):

        first = run_receptionist(self.workflow.id)

        second = run_receptionist(self.workflow.id)

        self.assertEqual(first.id, second.id)

        self.assertEqual(
            AgentExecution.objects.filter(
                workflow_run=self.workflow,
                agent_type=AgentExecution.AgentType.RECEPTIONIST,
            ).count(),
            1,
        )

    def test_reporter_email_is_not_in_agent_input(self):

        execution = run_receptionist(self.workflow.id)

        self.assertNotIn(
            "reporter_email",
            execution.input_payload,
        )

    def test_receptionist_failure_is_recorded(self):

        with patch(
            "apps.agents.runner.classify_ticket",
            side_effect=RuntimeError("Simulated classifier failure"),
        ):
            with self.assertRaises(RuntimeError):
                run_receptionist(self.workflow.id)

        execution = AgentExecution.objects.get(
            workflow_run=self.workflow,
            agent_type=AgentExecution.AgentType.RECEPTIONIST,
        )

        self.assertEqual(
            execution.status,
            AgentExecution.Status.FAILED,
        )

        self.assertEqual(
            execution.error_code,
            "RECEPTIONIST_EXECUTION_FAILED",
        )

        self.workflow.refresh_from_db()

        self.assertEqual(
            self.workflow.status,
            WorkflowRun.Status.FAILED,
        )

        self.ticket.refresh_from_db()

        self.assertEqual(
            self.ticket.status,
            Ticket.Status.IN_PROGRESS,
        )

    def test_receptionist_transient_failure_allows_retry(self):

        with patch(
            "apps.agents.runner.classify_ticket",
            side_effect=LLMTransientError(
                "Groq request timed out."
            ),
        ):
            with self.assertRaises(LLMTransientError):
                run_receptionist(self.workflow.id)

        first_execution = AgentExecution.objects.get(
            workflow_run=self.workflow,
            agent_type=AgentExecution.AgentType.RECEPTIONIST,
            attempt=1,
        )

        self.workflow.refresh_from_db()

        self.assertEqual(
            first_execution.status,
            AgentExecution.Status.FAILED,
        )

        self.assertEqual(
            first_execution.error_code,
            "LLM_TRANSIENT_FAILURE",
        )

        self.assertIsNotNone(first_execution.finished_at)

        self.assertEqual(
            self.workflow.status,
            WorkflowRun.Status.RUNNING,
        )

        self.assertIsNone(self.workflow.finished_at)

        # A subsequent invocation should create attempt 2.
        # The deterministic classifier is restored after the patch.
        second_execution = run_receptionist(self.workflow.id)

        self.assertEqual(second_execution.attempt, 2)

        self.assertEqual(
            second_execution.status,
            AgentExecution.Status.SUCCEEDED,
        )

        self.workflow.refresh_from_db()

        self.assertEqual(
            self.workflow.status,
            WorkflowRun.Status.RUNNING,
        )


    def test_redelivery_recovers_existing_receptionist_execution(self):
        task_id = "receptionist-worker-loss-test"

        execution = create_agent_execution(
            self.workflow.id,
            AgentExecution.AgentType.RECEPTIONIST,
            {"ticket_id": str(self.ticket.id)},
        )

        execution, claimed = start_agent_execution(
            execution.id,
            celery_task_id=task_id,
        )

        self.assertTrue(claimed)
        original_id = execution.id
        original_token = execution.claim_token

        recovered = run_receptionist(
            self.workflow.id,
            celery_task_id=task_id,
            redelivered=True,
        )

        recovered.refresh_from_db()

        self.assertEqual(recovered.id, original_id)
        self.assertEqual(recovered.attempt, 1)
        self.assertEqual(recovered.worker_loss_recoveries, 1)
        self.assertNotEqual(recovered.claim_token, original_token)

        self.assertEqual(
            recovered.status,
            AgentExecution.Status.SUCCEEDED,
        )

        self.assertEqual(
            AgentExecution.objects.filter(
                workflow_run=self.workflow,
                agent_type=AgentExecution.AgentType.RECEPTIONIST,
            ).count(),
            1,
        )
