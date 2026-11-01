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