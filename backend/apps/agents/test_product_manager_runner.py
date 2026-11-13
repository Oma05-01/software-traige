
from unittest.mock import patch

from django.test import TestCase
from apps.agents.llm.base import LLMTransientError
from apps.tickets.models import Ticket
from apps.workflow.models import WorkflowRun
from apps.workflow.services import (
    create_workflow_for_ticket,
    transition_workflow,
    advance_workflow_stage,
)
from apps.agents.models import AgentExecution

from .product_manager_runner import (
    ProductManagerNotReady,
    get_effective_receptionist_output,
    run_product_manager,
)


class ProductManagerRunnerTests(TestCase):

    def setUp(self):
        self.ticket = Ticket.objects.create(
            title="Add CSV export support",
            description="Please add CSV export functionality.",
            reporter_email="reporter@example.com",
            category=Ticket.Category.FEATURE,
            priority=Ticket.Priority.MEDIUM,
            status=Ticket.Status.IN_PROGRESS,
        )

        self.workflow = create_workflow_for_ticket(
            self.ticket.id
        )

        transition_workflow(
            self.workflow.id,
            WorkflowRun.Status.RUNNING,
        )

        advance_workflow_stage(
            self.workflow.id,
            WorkflowRun.Stage.PRODUCT_MANAGER,
        )

        # Preserve the original Receptionist classification.
        self.original_findings = {
            "category": "other",
            "priority": "unassessed",
            "classification_confidence": "low",
            "needs_human_review": True,
            "issue_summary": "An ambiguous report.",
        }

        self.receptionist_execution = AgentExecution.objects.create(
            workflow_run=self.workflow,
            agent_type=AgentExecution.AgentType.RECEPTIONIST,
            status=AgentExecution.Status.SUCCEEDED,
            output_payload=self.original_findings.copy(),
        )

    def test_effective_findings_use_staff_confirmed_classification(self):
        findings = get_effective_receptionist_output(
            self.workflow
        )

        self.assertEqual(
            findings["category"],
            Ticket.Category.FEATURE,
        )

        self.assertEqual(
            findings["priority"],
            Ticket.Priority.MEDIUM,
        )

        # Preserve other Receptionist findings.
        self.assertEqual(
            findings["classification_confidence"],
            "low",
        )

    @patch("apps.agents.product_manager_runner.assess_feature_request")
    def test_product_manager_receives_staff_confirmed_classification(
        self,
        mock_assessment,
    ):
        mock_assessment.return_value = {
            "assessment_status": "pending_human_review",
            "assessment_confidence": "medium",
            "acceptance_criteria": [
                "Users can export report data as CSV."
            ],
            "considerations": [],
            "open_questions": [],
            "requires_human_review": True,
            "approval_status": "not_approved",
        }

        execution = run_product_manager(
            self.workflow.id
        )

        self.assertEqual(
            execution.status,
            AgentExecution.Status.SUCCEEDED,
        )

        # Verify the actual assessment call.
        mock_assessment.assert_called_once()

        assessed_findings = mock_assessment.call_args.args[1]

        self.assertEqual(
            assessed_findings["category"],
            Ticket.Category.FEATURE,
        )

        self.assertEqual(
            assessed_findings["priority"],
            Ticket.Priority.MEDIUM,
        )

        # Verify the saved execution input.
        self.assertEqual(
            execution.input_payload[
                "receptionist_findings"
            ]["category"],
            Ticket.Category.FEATURE,
        )

        self.assertEqual(
            execution.input_payload[
                "receptionist_findings"
            ]["priority"],
            Ticket.Priority.MEDIUM,
        )

        # Verify original Receptionist history is unchanged.
        self.receptionist_execution.refresh_from_db()

        self.assertEqual(
            self.receptionist_execution.output_payload["category"],
            "other",
        )

        self.assertEqual(
            self.receptionist_execution.output_payload["priority"],
            "unassessed",
        )

        # Verify successful progression to Support Rep.
        self.workflow.refresh_from_db()

        self.assertEqual(
            self.workflow.current_stage,
            WorkflowRun.Stage.SUPPORT_REP,
        )

        self.assertEqual(
            self.workflow.status,
            WorkflowRun.Status.RUNNING,
        )

    @patch("apps.agents.product_manager_runner.assess_feature_request")
    def test_product_manager_rejects_non_feature_ticket(
        self,
        mock_assessment,
    ):
        self.ticket.category = Ticket.Category.BUG
        self.ticket.save(update_fields=["category"])

        with self.assertRaises(ProductManagerNotReady):
            run_product_manager(self.workflow.id)

        mock_assessment.assert_not_called()

        self.assertFalse(
            AgentExecution.objects.filter(
                workflow_run=self.workflow,
                agent_type=AgentExecution.AgentType.PRODUCT_MANAGER,
            ).exists()
        )

    @patch("apps.agents.product_manager_runner.assess_feature_request")
    def test_product_manager_transient_failure_allows_retry(
        self,
        mock_assessment,
    ):
        successful_result = {
            "assessment_status": "pending_human_review",
            "assessment_confidence": "medium",
            "acceptance_criteria": [
                "Users can export report data as CSV."
            ],
            "considerations": [],
            "open_questions": [],
            "requires_human_review": True,
            "approval_status": "not_approved",
        }

        mock_assessment.side_effect = [
            LLMTransientError("Groq request timed out."),
            successful_result,
        ]

        with self.assertRaises(LLMTransientError):
            run_product_manager(self.workflow.id)

        first_execution = AgentExecution.objects.get(
            workflow_run=self.workflow,
            agent_type=AgentExecution.AgentType.PRODUCT_MANAGER,
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

        # Second invocation should create attempt 2.
        second_execution = run_product_manager(self.workflow.id)

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

        self.assertEqual(mock_assessment.call_count, 2)
