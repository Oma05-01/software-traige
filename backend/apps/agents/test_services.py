from django.test import TestCase

from apps.tickets.models import Ticket
from apps.workflow.models import WorkflowRun
from apps.workflow.services import transition_workflow
from apps.events.models import WorkflowEvent

from .models import AgentExecution
from .services import (
    ActiveAgentExecutionExists,
    WorkflowNotRunning,
    InvalidAgentExecutionTransition,
    StaleAgentExecutionClaim,
    create_agent_execution,
    start_agent_execution,
    complete_agent_execution,
    fail_agent_execution,
    skip_agent_execution,
)


class AgentExecutionServiceTests(TestCase):

    def setUp(self):
        self.ticket = Ticket.objects.create(
            title="PDF upload failure",
            description="Upload crashes above 25 MB.",
            reporter_email="reporter@example.com",
        )

        self.workflow = WorkflowRun.objects.create(
            ticket=self.ticket,
        )

        self.workflow = transition_workflow(
            self.workflow.id,
            WorkflowRun.Status.RUNNING,
        )

    def create_execution(self, **kwargs):
        defaults = {
            "workflow_id": self.workflow.id,
            "agent_type": AgentExecution.AgentType.RECEPTIONIST,
            "input_payload": {
                "ticket_id": str(self.ticket.id),
            },
        }

        defaults.update(kwargs)

        return create_agent_execution(**defaults)

    def test_create_execution(self):
        execution = self.create_execution()

        self.assertEqual(
            execution.status,
            AgentExecution.Status.QUEUED,
        )

        self.assertEqual(execution.attempt, 1)

        self.assertEqual(
            execution.agent_type,
            AgentExecution.AgentType.RECEPTIONIST,
        )

    def test_creation_updates_workflow_stage(self):
        execution = self.create_execution(
            agent_type=AgentExecution.AgentType.DEBUGGER,
        )

        self.workflow.refresh_from_db()

        self.assertEqual(
            self.workflow.current_stage,
            WorkflowRun.Stage.DEBUGGER,
        )

        self.assertTrue(
            WorkflowEvent.objects.filter(
                workflow_run=self.workflow,
                event_type="workflow.stage_changed",
                payload__execution_id=str(execution.id),
            ).exists()
        )

    def test_invalid_agent_type_is_rejected(self):
        with self.assertRaises(ValueError):
            self.create_execution(
                agent_type="unknown_agent",
            )

    def test_non_running_workflow_rejects_assignment(self):
        queued_ticket = Ticket.objects.create(
            title="Another issue",
            description="Another issue description.",
            reporter_email="another@example.com",
        )

        queued_workflow = WorkflowRun.objects.create(
            ticket=queued_ticket,
        )

        with self.assertRaises(WorkflowNotRunning):
            create_agent_execution(
                queued_workflow.id,
                AgentExecution.AgentType.RECEPTIONIST,
            )

    def test_duplicate_active_execution_is_rejected(self):
        self.create_execution()

        with self.assertRaises(ActiveAgentExecutionExists):
            self.create_execution(
                agent_type=AgentExecution.AgentType.DEBUGGER,
            )

    def test_start_execution(self):
        execution = self.create_execution()

        execution, claimed = start_agent_execution(
            execution.id,
            celery_task_id="task-123",
        )

        self.assertTrue(claimed)

        self.assertEqual(
            execution.status,
            AgentExecution.Status.RUNNING,
        )

        self.assertEqual(
            execution.celery_task_id,
            "task-123",
        )

        self.assertIsNotNone(execution.started_at)

    def test_duplicate_start_does_not_claim_execution(self):
        execution = self.create_execution()

        start_agent_execution(execution.id)

        event_count = WorkflowEvent.objects.filter(
            workflow_run=self.workflow,
            event_type="agent.started",
        ).count()

        execution, claimed = start_agent_execution(
            execution.id,
            celery_task_id="duplicate-task",
        )

        self.assertFalse(claimed)

        self.assertEqual(
            execution.celery_task_id,
            "",
        )

        self.assertEqual(
            WorkflowEvent.objects.filter(
                workflow_run=self.workflow,
                event_type="agent.started",
            ).count(),
            event_count,
        )

    def test_complete_execution(self):
        execution = self.create_execution()

        start_agent_execution(execution.id)

        output = {
            "category": "bug",
            "priority": "high",
            "confidence": 0.94,
        }

        execution = complete_agent_execution(
            execution.id,
            output_payload=output,
        )

        self.assertEqual(
            execution.status,
            AgentExecution.Status.SUCCEEDED,
        )

        self.assertEqual(
            execution.output_payload,
            output,
        )

        self.assertIsNotNone(execution.finished_at)

    def test_completion_is_idempotent(self):
        execution = self.create_execution()

        start_agent_execution(execution.id)

        complete_agent_execution(
            execution.id,
            {"result": "success"},
        )

        event_count = WorkflowEvent.objects.filter(
            workflow_run=self.workflow,
            event_type="agent.completed",
        ).count()

        complete_agent_execution(
            execution.id,
            {"result": "duplicate"},
        )

        execution.refresh_from_db()

        self.assertEqual(
            execution.output_payload,
            {"result": "success"},
        )

        self.assertEqual(
            WorkflowEvent.objects.filter(
                workflow_run=self.workflow,
                event_type="agent.completed",
            ).count(),
            event_count,
        )

    def test_fail_execution(self):
        execution = self.create_execution()

        start_agent_execution(execution.id)

        execution = fail_agent_execution(
            execution.id,
            error_code="LLM_TIMEOUT",
            error_message="The provider timed out.",
        )

        self.assertEqual(
            execution.status,
            AgentExecution.Status.FAILED,
        )

        self.assertEqual(
            execution.error_code,
            "LLM_TIMEOUT",
        )

        self.assertIsNotNone(execution.finished_at)

    def test_failed_execution_allows_retry(self):
        execution = self.create_execution()

        start_agent_execution(execution.id)

        fail_agent_execution(
            execution.id,
            "LLM_TIMEOUT",
            "Provider timeout.",
        )

        retry = self.create_execution()

        self.assertEqual(retry.attempt, 2)

        self.assertEqual(
            retry.status,
            AgentExecution.Status.QUEUED,
        )

    
    def test_stale_claim_cannot_complete_recovered_execution(self):
        execution = self.create_execution()

        execution, claimed = start_agent_execution(
            execution.id,
            celery_task_id="worker-task-123",
        )

        self.assertTrue(claimed)
        original_token = execution.claim_token

        recovered, claimed = start_agent_execution(
            execution.id,
            celery_task_id="worker-task-123",
            redelivered=True,
        )

        self.assertTrue(claimed)

        with self.assertRaises(StaleAgentExecutionClaim):
            complete_agent_execution(
                execution.id,
                output_payload={"result": "stale"},
                claim_token=original_token,
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

    def test_stale_claim_cannot_fail_recovered_execution(self):
        execution = self.create_execution()

        execution, claimed = start_agent_execution(
            execution.id,
            celery_task_id="worker-task-456",
        )

        self.assertTrue(claimed)
        original_token = execution.claim_token

        recovered, claimed = start_agent_execution(
            execution.id,
            celery_task_id="worker-task-456",
            redelivered=True,
        )

        self.assertTrue(claimed)

        with self.assertRaises(StaleAgentExecutionClaim):
            fail_agent_execution(
                execution.id,
                error_code="STALE_WORKER_FAILURE",
                error_message="Old worker attempted to fail execution.",
                claim_token=original_token,
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

    def test_current_claim_can_complete_recovered_execution(self):
        execution = self.create_execution()

        execution, claimed = start_agent_execution(
            execution.id,
            celery_task_id="worker-task-789",
        )

        self.assertTrue(claimed)

        recovered, claimed = start_agent_execution(
            execution.id,
            celery_task_id="worker-task-789",
            redelivered=True,
        )

        self.assertTrue(claimed)

        completed = complete_agent_execution(
            execution.id,
            output_payload={"result": "recovered"},
            claim_token=recovered.claim_token,
        )

        self.assertEqual(
            completed.status,
            AgentExecution.Status.SUCCEEDED,
        )

        self.assertEqual(
            completed.output_payload,
            {"result": "recovered"},
        )


    def test_skip_queued_execution(self):
        execution = self.create_execution()

        execution = skip_agent_execution(execution.id)

        self.assertEqual(
            execution.status,
            AgentExecution.Status.SKIPPED,
        )

        self.assertIsNotNone(execution.finished_at)

    def test_running_execution_cannot_be_skipped(self):
        execution = self.create_execution()

        start_agent_execution(execution.id)

        with self.assertRaises(
            InvalidAgentExecutionTransition
        ):
            skip_agent_execution(execution.id)

    def test_agent_payload_must_be_dictionary(self):
        with self.assertRaises(TypeError):
            self.create_execution(
                input_payload="not-a-dictionary",
            )


    def test_initial_claim_creates_fencing_token(self):
        execution = self.create_execution()

        execution, claimed = start_agent_execution(
            execution.id,
            celery_task_id="task-123",
        )

        self.assertTrue(claimed)
        self.assertIsNotNone(execution.claim_token)
        self.assertEqual(execution.worker_loss_recoveries, 0)

    def test_redelivered_task_recovers_same_execution(self):
        execution = self.create_execution()

        execution, claimed = start_agent_execution(
            execution.id,
            celery_task_id="task-123",
        )

        self.assertTrue(claimed)

        original_id = execution.id
        original_attempt = execution.attempt
        original_token = execution.claim_token

        recovered, claimed = start_agent_execution(
            execution.id,
            celery_task_id="task-123",
            redelivered=True,
        )

        self.assertTrue(claimed)
        self.assertEqual(recovered.id, original_id)
        self.assertEqual(recovered.attempt, original_attempt)
        self.assertEqual(recovered.worker_loss_recoveries, 1)
        self.assertNotEqual(
            recovered.claim_token,
            original_token,
        )

        self.assertEqual(
            WorkflowEvent.objects.filter(
                workflow_run=self.workflow,
                event_type="agent.worker_loss_recovered",
            ).count(),
            1,
        )

    def test_redelivery_with_different_task_id_cannot_reclaim(self):
        execution = self.create_execution()

        execution, claimed = start_agent_execution(
            execution.id,
            celery_task_id="original-task",
        )

        original_token = execution.claim_token

        recovered, claimed = start_agent_execution(
            execution.id,
            celery_task_id="different-task",
            redelivered=True,
        )

        self.assertFalse(claimed)
        self.assertEqual(
            recovered.claim_token,
            original_token,
        )
        self.assertEqual(
            recovered.worker_loss_recoveries,
            0,
        )

        self.assertFalse(
            WorkflowEvent.objects.filter(
                workflow_run=self.workflow,
                event_type="agent.worker_loss_recovered",
            ).exists()
        )

    def test_queued_redelivery_does_not_count_as_recovery(self):
        execution = self.create_execution()

        execution, claimed = start_agent_execution(
            execution.id,
            celery_task_id="task-queued",
            redelivered=True,
        )

        self.assertTrue(claimed)
        self.assertEqual(
            execution.status,
            AgentExecution.Status.RUNNING,
        )
        self.assertEqual(execution.worker_loss_recoveries, 0)

    def test_worker_loss_recovery_budget_exhaustion_fails_workflow(self):
        execution = self.create_execution()

        execution, claimed = start_agent_execution(
            execution.id,
            celery_task_id="task-123",
        )

        self.assertTrue(claimed)

        # Allow exactly two recoveries of this execution.
        for expected_recoveries in (1, 2):
            execution, claimed = start_agent_execution(
                execution.id,
                celery_task_id="task-123",
                redelivered=True,
            )

            self.assertTrue(claimed)
            self.assertEqual(
                execution.worker_loss_recoveries,
                expected_recoveries,
            )

        # The next worker-loss redelivery exhausts the budget.
        execution, claimed = start_agent_execution(
            execution.id,
            celery_task_id="task-123",
            redelivered=True,
        )

        self.assertFalse(claimed)

        execution.refresh_from_db()
        self.workflow.refresh_from_db()

        self.assertEqual(
            execution.status,
            AgentExecution.Status.FAILED,
        )

        self.assertEqual(
            execution.error_code,
            "WORKER_LOSS_RECOVERY_EXHAUSTED",
        )

        self.assertEqual(
            execution.worker_loss_recoveries,
            2,
        )

        self.assertIsNotNone(execution.finished_at)

        self.assertEqual(
            self.workflow.status,
            WorkflowRun.Status.FAILED,
        )

        self.assertEqual(
            self.workflow.error_code,
            "AGENT_WORKER_LOSS_EXHAUSTED",
        )

        self.assertTrue(
            WorkflowEvent.objects.filter(
                workflow_run=self.workflow,
                event_type=(
                    "workflow.agent_worker_loss_recovery_exhausted"
                ),
            ).exists()
        )
