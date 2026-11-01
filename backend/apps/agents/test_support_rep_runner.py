from unittest.mock import patch
from apps.reviews.models import ReviewRequest
from django.test import TestCase

from apps.agents.models import AgentExecution
from apps.agents.services import (
    complete_agent_execution,
    create_agent_execution,
    start_agent_execution,
)
from apps.agents.support_rep_runner import (
    SupportRepNotReady,
    run_support_rep,
)
from apps.events.models import WorkflowEvent
from apps.tickets.models import Ticket
from apps.workflow.models import WorkflowRun
from apps.workflow.services import (
    advance_workflow_stage,
    create_workflow_for_ticket,
    transition_workflow,
)


class SupportRepRunnerTests(TestCase):

    def setUp(self):
        self.ticket = Ticket.objects.create(
            title="Frontend hangs during report generation",
            description=(
                "The dashboard freezes when generating "
                "reports containing more than 500 records."
            ),
            reporter_name="Test Reporter",
            reporter_email="reporter@example.com",
            environment="Windows 11, Chrome",
            steps_to_reproduce=(
                "Open reports, select more than 500 records "
                "and click Generate."
            ),
            expected_behavior="The report should generate.",
            actual_behavior="The dashboard becomes unresponsive.",
            category=Ticket.Category.BUG,
            priority=Ticket.Priority.MEDIUM,
        )

        self.workflow = create_workflow_for_ticket(
            self.ticket.id
        )

        transition_workflow(
            self.workflow.id,
            WorkflowRun.Status.RUNNING,
        )

        receptionist_output = {
            "category": "bug",
            "priority": "medium",
            "issue_summary": self.ticket.title,
            "needs_human_review": False,
        }

        receptionist_execution = create_agent_execution(
            self.workflow.id,
            "receptionist",
            {
                "ticket_id": str(self.ticket.id),
            },
        )

        receptionist_execution, _ = start_agent_execution(
            receptionist_execution.id,
        )

        complete_agent_execution(
            receptionist_execution.id,
            receptionist_output,
        )

        debugger_output = {
            "investigation_status": "no_relevant_evidence",
            "summary": "No relevant documentation was retrieved.",
            "documented_evidence": [],
            "root_cause": {
                "status": "not_established",
                "explanation": "Insufficient evidence.",
            },
            "possible_explanations": [],
            "recommended_workaround": None,
            "unresolved_questions": [
                "Additional technical documentation is needed."
            ],
        }

        debugger_execution = create_agent_execution(
            self.workflow.id,
            "debugger",
            {
                "ticket_id": str(self.ticket.id),
            },
        )

        debugger_execution, _ = start_agent_execution(
            debugger_execution.id,
        )

        complete_agent_execution(
            debugger_execution.id,
            debugger_output,
        )

        advance_workflow_stage(
            self.workflow.id,
            WorkflowRun.Stage.SUPPORT_REP,
        )

    def test_support_rep_completes_and_moves_to_human_review(self):
        execution = run_support_rep(self.workflow.id)

        execution.refresh_from_db()
        self.workflow.refresh_from_db()
        self.ticket.refresh_from_db()

        self.assertEqual(
            execution.agent_type,
            "support_rep",
        )

        self.assertEqual(
            execution.status,
            AgentExecution.Status.SUCCEEDED,
        )

        review_request = ReviewRequest.objects.get(
            agent_execution=execution,
            action_type=ReviewRequest.ActionType.SEND_SUPPORT_RESPONSE,
        )

        self.assertEqual(
            review_request.status,
            ReviewRequest.Status.PENDING,
        )

        self.assertEqual(
            review_request.workflow_run,
            self.workflow,
        )

        self.assertEqual(
            review_request.proposed_payload,
            execution.output_payload,
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

    def test_support_rep_persists_draft_output(self):
        execution = run_support_rep(self.workflow.id)

        self.assertEqual(
            execution.output_payload["draft_status"],
            "pending_human_review",
        )

        self.assertTrue(
            execution.output_payload["requires_human_review"]
        )

        self.assertFalse(
            execution.output_payload["external_send_authorized"]
        )

        self.assertTrue(
            execution.output_payload["draft_response"]
        )

    def test_support_rep_input_excludes_reporter_email(self):
        execution = run_support_rep(self.workflow.id)

        self.assertNotIn(
            "reporter_email",
            execution.input_payload,
        )

        self.assertIn(
            "debugger_findings",
            execution.input_payload,
        )

        self.assertIn(
            "receptionist_findings",
            execution.input_payload,
        )

    def test_support_rep_records_workflow_event(self):
        run_support_rep(self.workflow.id)

        event = WorkflowEvent.objects.filter(
            workflow_run=self.workflow,
            event_type="support.response_drafted",
        ).first()

        self.assertIsNotNone(event)

        self.assertTrue(
            event.payload["requires_human_review"]
        )

        self.assertFalse(
            event.payload["external_send_authorized"]
        )

        review_event = WorkflowEvent.objects.get(
            workflow_run=self.workflow,
            event_type="review.requested",
        )

        self.assertTrue(
            review_event.payload["review_request_id"]
        )

    def test_duplicate_invocation_does_not_create_another_execution(self):
        first_execution = run_support_rep(self.workflow.id)

        second_execution = run_support_rep(self.workflow.id)

        self.assertEqual(
            first_execution.id,
            second_execution.id,
        )

        self.assertEqual(
            AgentExecution.objects.filter(
                workflow_run=self.workflow,
                agent_type="support_rep",
            ).count(),
            1,
        )

    def test_support_rep_requires_running_workflow(self):
        transition_workflow(
            self.workflow.id,
            WorkflowRun.Status.FAILED,
        )

        with self.assertRaises(SupportRepNotReady):
            run_support_rep(self.workflow.id)

    def test_support_rep_rejects_wrong_stage(self):
        advance_workflow_stage(
            self.workflow.id,
            WorkflowRun.Stage.HUMAN_REVIEW,
        )

        with self.assertRaises(SupportRepNotReady):
            run_support_rep(self.workflow.id)

    def test_support_rep_requires_successful_debugger_execution(self):
        AgentExecution.objects.filter(
            workflow_run=self.workflow,
            agent_type="debugger",
        ).delete()

        with self.assertRaises(SupportRepNotReady):
            run_support_rep(self.workflow.id)

        self.assertFalse(
            AgentExecution.objects.filter(
                workflow_run=self.workflow,
                agent_type="support_rep",
            ).exists()
        )

    @patch(
        "apps.agents.support_rep_runner.draft_support_response",
        side_effect=RuntimeError("Simulated drafting failure"),
    )
    def test_failure_marks_execution_and_workflow_failed(
        self,
        mock_drafting,
    ):
        with self.assertRaises(RuntimeError):
            run_support_rep(
                self.workflow.id,
                celery_task_id="test-support-task",
            )

        self.workflow.refresh_from_db()

        execution = AgentExecution.objects.get(
            workflow_run=self.workflow,
            agent_type="support_rep",
        )

        self.assertEqual(
            execution.status,
            AgentExecution.Status.FAILED,
        )

        self.assertEqual(
            execution.error_code,
            "RuntimeError",
        )

        self.assertEqual(
            self.workflow.status,
            WorkflowRun.Status.FAILED,
        )