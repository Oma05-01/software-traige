from unittest.mock import patch

from django.test import TestCase, override_settings

from apps.tickets.models import Ticket
from apps.workflow.models import WorkflowRun
from apps.workflow.services import (
    create_workflow_for_ticket,
    transition_workflow,
    advance_workflow_stage,
)
from apps.agents.models import AgentExecution
from apps.events.models import WorkflowEvent
from apps.agents.llm.base import LLMTransientError
from apps.knowledge.services import ingest_document
from apps.agents.services import (
    create_agent_execution,
    start_agent_execution,
)
from .debugger_runner import (
    DebuggerNotReady,
    run_debugger,
)

@override_settings(DEBUGGER_MODE="deterministic")
class DebuggerRunnerTests(TestCase):

    def setUp(self):

        self.ticket = Ticket.objects.create(
            title="PDF upload failure",
            description=(
                "The application fails when uploading "
                "PDF files larger than 25 MB."
            ),
            reporter_email="reporter@example.com",
            environment="Windows 11, Chrome",
            category=Ticket.Category.BUG,
            priority=Ticket.Priority.HIGH,
            status=Ticket.Status.IN_PROGRESS,
        )

        self.document = ingest_document(
            title="PDF Upload Troubleshooting",
            content=(
                "The PDF upload endpoint rejects files "
                "larger than 25 MB. "
                "The upload service validates file sizes "
                "before processing."
            ),
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
            WorkflowRun.Stage.DEBUGGER,
        )

        # Create a successful Receptionist execution.
        AgentExecution.objects.create(
            workflow_run=self.workflow,
            agent_type=AgentExecution.AgentType.RECEPTIONIST,
            status=AgentExecution.Status.SUCCEEDED,
            output_payload={
                "category": "bug",
                "priority": "high",
                "classification_confidence": "high",
            },
        )

    def test_debugger_executes_successfully(self):

        execution = run_debugger(self.workflow.id)

        self.ticket.refresh_from_db()
        self.workflow.refresh_from_db()

        self.assertEqual(
            execution.status,
            AgentExecution.Status.SUCCEEDED,
        )

        self.assertEqual(
            execution.output_payload["investigation_status"],
            "evidence_found",
        )

        self.assertEqual(
            self.workflow.current_stage,
            WorkflowRun.Stage.SUPPORT_REP,
        )

        self.assertEqual(
            self.workflow.status,
            WorkflowRun.Status.RUNNING,
        )

    def test_investigation_contains_document_evidence(self):

        execution = run_debugger(self.workflow.id)

        evidence = execution.output_payload[
            "documented_evidence"
        ]

        self.assertGreater(len(evidence), 0)

        self.assertEqual(
            evidence[0]["document_id"],
            str(self.document.id),
        )

    def test_debugger_does_not_invent_root_cause(self):

        execution = run_debugger(self.workflow.id)

        self.assertEqual(
            execution.output_payload["root_cause"]["status"],
            "not_established",
        )

    def test_reporter_email_is_not_in_debugger_input(self):

        execution = run_debugger(self.workflow.id)

        self.assertNotIn(
            "reporter_email",
            execution.input_payload,
        )

    def test_repeated_invocation_does_not_duplicate_execution(self):

        first = run_debugger(self.workflow.id)

        second = run_debugger(self.workflow.id)

        self.assertEqual(first.id, second.id)

        self.assertEqual(
            AgentExecution.objects.filter(
                workflow_run=self.workflow,
                agent_type=AgentExecution.AgentType.DEBUGGER,
            ).count(),
            1,
        )

    def test_no_evidence_still_advances_to_support_rep(self):

        with patch(
            "apps.agents.debugger_runner.investigate_ticket"
        ) as mock_investigation:

            mock_investigation.return_value = {
                "investigation_status": "no_relevant_evidence",
                "documented_evidence": [],
                "root_cause": {
                    "status": "not_established",
                },
                "retrieval_metadata": {
                    "evidence_count": 0,
                },
            }

            execution = run_debugger(self.workflow.id)

        self.assertEqual(
            execution.status,
            AgentExecution.Status.SUCCEEDED,
        )

        self.workflow.refresh_from_db()

        self.assertEqual(
            self.workflow.current_stage,
            WorkflowRun.Stage.SUPPORT_REP,
        )


    def test_redelivery_recovers_existing_debugger_execution(self):
        task_id = "debugger-worker-loss-test"

        execution = create_agent_execution(
            self.workflow.id,
            AgentExecution.AgentType.DEBUGGER,
            {"ticket_id": str(self.ticket.id)},
        )

        execution, claimed = start_agent_execution(
            execution.id,
            celery_task_id=task_id,
        )

        self.assertTrue(claimed)
        original_id = execution.id
        original_token = execution.claim_token

        recovered = run_debugger(
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
                agent_type=AgentExecution.AgentType.DEBUGGER,
            ).count(),
            1,
        )


    def test_debugger_failure_is_recorded(self):

        with patch(
            "apps.agents.debugger_runner.investigate_ticket",
            side_effect=RuntimeError("Simulated investigation failure"),
        ):

            with self.assertRaises(RuntimeError):
                run_debugger(self.workflow.id)

        execution = AgentExecution.objects.get(
            workflow_run=self.workflow,
            agent_type=AgentExecution.AgentType.DEBUGGER,
        )

        self.workflow.refresh_from_db()

        self.assertEqual(
            execution.status,
            AgentExecution.Status.FAILED,
        )

        self.assertEqual(
            execution.error_code,
            "DEBUGGER_EXECUTION_FAILED",
        )

        self.assertEqual(
            self.workflow.status,
            WorkflowRun.Status.FAILED,
        )

    def test_debugger_requires_successful_receptionist(self):

        AgentExecution.objects.filter(
            workflow_run=self.workflow,
            agent_type=AgentExecution.AgentType.RECEPTIONIST,
        ).delete()

        with self.assertRaises(DebuggerNotReady):
            run_debugger(self.workflow.id)

        self.assertFalse(
            AgentExecution.objects.filter(
                workflow_run=self.workflow,
                agent_type=AgentExecution.AgentType.DEBUGGER,
            ).exists()
        )

    def test_debugger_rejects_wrong_workflow_stage(self):

        self.workflow.current_stage = WorkflowRun.Stage.RECEPTIONIST

        self.workflow.save(
            update_fields=["current_stage"]
        )

        with self.assertRaises(DebuggerNotReady):
            run_debugger(self.workflow.id)

    def test_debugger_transient_failure_allows_retry(self):

        with patch(
            "apps.agents.debugger_runner.investigate_ticket",
            side_effect=LLMTransientError(
                "Groq request timed out."
            ),
        ):
            with self.assertRaises(LLMTransientError):
                run_debugger(self.workflow.id)

        first_execution = AgentExecution.objects.get(
            workflow_run=self.workflow,
            agent_type=AgentExecution.AgentType.DEBUGGER,
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

        # Retry using the deterministic Debugger implementation.
        second_execution = run_debugger(self.workflow.id)

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
