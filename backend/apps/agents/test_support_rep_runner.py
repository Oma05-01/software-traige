from unittest.mock import patch
from apps.reviews.models import ReviewRequest
from django.test import TestCase
from django.test import override_settings
from apps.agents.models import AgentExecution
from apps.agents.services import (
    complete_agent_execution,
    create_agent_execution,
    start_agent_execution,
)
from apps.agents.services import StaleAgentExecutionClaim
from apps.agents.llm.base import LLMTransientError
from apps.agents.support_rep_runner import (
    SupportRepNotReady,
    get_support_rep_drafter,
    run_support_rep,
    build_support_rep_input,
    get_support_context,
    persist_support_response
)
from apps.events.models import WorkflowEvent
from apps.tickets.models import Ticket
from apps.workflow.models import WorkflowRun
from apps.workflow.services import (
    advance_workflow_stage,
    create_workflow_for_ticket,
    transition_workflow,
)

@override_settings(SUPPORT_REP_MODE="deterministic")
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

    def test_transient_failure_allows_retry_without_duplicate_review(
        self,
    ):
        with patch(
            "apps.agents.support_rep_runner.draft_support_response",
            side_effect=LLMTransientError(
                "Groq request timed out."
            ),
        ) as mock_drafting:
            with self.assertRaises(LLMTransientError):
                run_support_rep(self.workflow.id)

            mock_drafting.assert_called_once()

        first_execution = AgentExecution.objects.get(
            workflow_run=self.workflow,
            agent_type="support_rep",
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

        # No review request should exist for the failed attempt.
        self.assertFalse(
            ReviewRequest.objects.filter(
                agent_execution__workflow_run=self.workflow,
            ).exists()
        )

        # The real deterministic implementation runs on retry.
        second_execution = run_support_rep(self.workflow.id)

        self.assertEqual(second_execution.attempt, 2)

        self.assertEqual(
            second_execution.status,
            AgentExecution.Status.SUCCEEDED,
        )

        self.workflow.refresh_from_db()

        self.assertEqual(
            self.workflow.status,
            WorkflowRun.Status.AWAITING_REVIEW,
        )

        self.assertEqual(
            self.workflow.current_stage,
            WorkflowRun.Stage.HUMAN_REVIEW,
        )

        # Exactly one review request should exist.
        review_requests = ReviewRequest.objects.filter(
            agent_execution__workflow_run=self.workflow,
            action_type=(
                ReviewRequest.ActionType.SEND_SUPPORT_RESPONSE
            ),
        )

        self.assertEqual(review_requests.count(), 1)

        review_request = review_requests.get()

        self.assertEqual(
            review_request.agent_execution_id,
            second_execution.id,
        )

        self.assertEqual(
            review_request.status,
            ReviewRequest.Status.PENDING,
        )

class FeatureSupportRepContextTests(TestCase):
    def setUp(self):
        self.ticket = Ticket.objects.create(
            title="Add dark mode to the dashboard",
            description=(
                "Users should be able to switch between "
                "light and dark themes."
            ),
            reporter_name="Feature Requester",
            reporter_email="feature@example.com",
            environment="Windows 11, Chrome",
            category=Ticket.Category.FEATURE,
            priority=Ticket.Priority.MEDIUM,
        )

        self.workflow = create_workflow_for_ticket(
            self.ticket.id
        )

        transition_workflow(
            self.workflow.id,
            WorkflowRun.Status.RUNNING,
        )

        self.receptionist_output = {
            "category": "feature",
            "priority": "medium",
            "issue_summary": self.ticket.title,
            "needs_human_review": False,
        }

        receptionist_execution = create_agent_execution(
            self.workflow.id,
            "receptionist",
            {"ticket_id": str(self.ticket.id)},
        )

        receptionist_execution, _ = start_agent_execution(
            receptionist_execution.id,
        )

        complete_agent_execution(
            receptionist_execution.id,
            self.receptionist_output,
        )

        advance_workflow_stage(
            self.workflow.id,
            WorkflowRun.Stage.PRODUCT_MANAGER,
        )

        self.product_manager_output = {
            "assessment_status": "pending_human_review",
            "problem_statement": (
                "The dashboard currently offers only a light theme."
            ),
            "requested_capability": (
                "Allow users to switch between light and dark themes."
            ),
            "user_value": (
                "Users can choose their preferred display theme."
            ),
            "proposed_scope": (
                "Provide a dashboard-level theme preference."
            ),
            "acceptance_criteria": [
                "Users can select a dark theme.",
                "The selected theme is applied consistently.",
            ],
            "considerations": [
                "Theme preference persistence needs consideration."
            ],
            "open_questions": [
                "Should the preference persist across devices?"
            ],
            "assessment_confidence": "high",
            "requires_human_review": True,
            "approval_status": "not_approved",
        }

        product_manager_execution = create_agent_execution(
            self.workflow.id,
            "product_manager",
            {"ticket_id": str(self.ticket.id)},
        )

        product_manager_execution, _ = start_agent_execution(
            product_manager_execution.id,
        )

        complete_agent_execution(
            product_manager_execution.id,
            self.product_manager_output,
        )

        advance_workflow_stage(
            self.workflow.id,
            WorkflowRun.Stage.SUPPORT_REP,
        )

    def test_feature_ticket_uses_product_manager_findings(self):
        support_context = get_support_context(self.workflow)

        self.assertIsNone(
            support_context["debugger_findings"]
        )

        self.assertEqual(
            support_context["product_manager_findings"],
            self.product_manager_output,
        )

    def test_feature_support_input_contains_product_assessment(self):
        support_context = get_support_context(self.workflow)

        input_payload = build_support_rep_input(
            self.ticket,
            self.receptionist_output,
            **support_context,
        )

        self.assertIsInstance(input_payload, dict)

        self.assertIsNone(
            input_payload["debugger_findings"]
        )

        self.assertEqual(
            input_payload["product_manager_findings"],
            self.product_manager_output,
        )

        self.assertNotIn(
            "reporter_email",
            input_payload,
        )


    @override_settings(SUPPORT_REP_MODE="llm")
    def test_selects_llm_support_rep_implementation(self):
        from apps.agents.implementations.support_rep_llm import (
            draft_support_response_llm,
        )

        self.assertIs(
            get_support_rep_drafter(),
            draft_support_response_llm,
        )


    def test_redelivery_recovers_existing_support_rep_execution(self):
        task_id = "support-rep-worker-loss-test"

        execution = create_agent_execution(
            self.workflow.id,
            AgentExecution.AgentType.SUPPORT_REP,
            {"ticket_id": str(self.ticket.id)},
        )

        execution, claimed = start_agent_execution(
            execution.id,
            celery_task_id=task_id,
        )

        self.assertTrue(claimed)
        original_id = execution.id
        original_token = execution.claim_token

        recovered = run_support_rep(
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
                agent_type=AgentExecution.AgentType.SUPPORT_REP,
            ).count(),
            1,
        )

        self.assertEqual(
            ReviewRequest.objects.filter(
                agent_execution__workflow_run=self.workflow,
            ).count(),
            1,
        )

        self.workflow.refresh_from_db()

        self.assertEqual(
            self.workflow.status,
            WorkflowRun.Status.AWAITING_REVIEW,
        )


    def test_stale_worker_cannot_create_support_review_request(self):
        execution = create_agent_execution(
            self.workflow.id,
            AgentExecution.AgentType.SUPPORT_REP,
            {"ticket_id": str(self.ticket.id)},
        )

        execution, claimed = start_agent_execution(
            execution.id,
            celery_task_id="support-rep-stale-worker-test",
        )

        self.assertTrue(claimed)
        stale_token = execution.claim_token

        recovered, claimed = start_agent_execution(
            execution.id,
            celery_task_id="support-rep-stale-worker-test",
            redelivered=True,
        )

        self.assertTrue(claimed)

        result = {
            "draft_status": "pending_human_review",
            "external_send_authorized": False,
            "response_type": "technical_guidance",
            "evidence_references": [],
            "follow_up_questions": [],
        }

        with self.assertRaises(StaleAgentExecutionClaim):
            persist_support_response(
                execution,
                result,
                claim_token=stale_token,
            )

        self.assertFalse(
            ReviewRequest.objects.filter(
                agent_execution__workflow_run=self.workflow,
            ).exists()
        )

        execution.refresh_from_db()

        self.assertEqual(
            execution.status,
            AgentExecution.Status.RUNNING,
        )

        self.assertEqual(
            execution.claim_token,
            recovered.claim_token,
        )

        self.workflow.refresh_from_db()

        self.assertEqual(
            self.workflow.status,
            WorkflowRun.Status.RUNNING,
        )
