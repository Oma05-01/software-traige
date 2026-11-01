from django.db import IntegrityError, transaction
from django.test import TestCase

from apps.tickets.models import Ticket
from apps.workflow.models import WorkflowRun

from .models import AgentExecution


class AgentExecutionModelTests(TestCase):

    def setUp(self):
        self.ticket = Ticket.objects.create(
            title="PDF upload failure",
            description="Upload crashes above 25 MB.",
            reporter_email="reporter@example.com",
        )

        self.workflow = WorkflowRun.objects.create(
            ticket=self.ticket,
        )

    def create_execution(self, **kwargs):
        defaults = {
            "workflow_run": self.workflow,
            "agent_type": AgentExecution.AgentType.RECEPTIONIST,
            "attempt": 1,
        }

        defaults.update(kwargs)

        return AgentExecution.objects.create(**defaults)

    def test_create_agent_execution(self):
        execution = self.create_execution()

        self.assertEqual(
            execution.status,
            AgentExecution.Status.QUEUED,
        )

        self.assertEqual(execution.attempt, 1)

    def test_input_and_output_payloads_default_to_empty_dicts(self):
        execution = self.create_execution()

        self.assertEqual(execution.input_payload, {})
        self.assertEqual(execution.output_payload, {})

    def test_agent_attempt_numbers_must_be_unique(self):
        self.create_execution()

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self.create_execution()

    def test_only_one_active_agent_per_workflow(self):
        self.create_execution()

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self.create_execution(
                    agent_type=AgentExecution.AgentType.DEBUGGER,
                )

    def test_failed_execution_allows_another_attempt(self):
        first = self.create_execution()

        first.status = AgentExecution.Status.FAILED
        first.save(update_fields=["status"])

        second = self.create_execution(attempt=2)

        self.assertEqual(first.attempt, 1)
        self.assertEqual(second.attempt, 2)

        self.assertEqual(
            second.status,
            AgentExecution.Status.QUEUED,
        )

    def test_completed_execution_allows_next_agent(self):
        self.create_execution(
            status=AgentExecution.Status.SUCCEEDED,
        )

        debugger = self.create_execution(
            agent_type=AgentExecution.AgentType.DEBUGGER,
        )

        self.assertEqual(
            debugger.agent_type,
            AgentExecution.AgentType.DEBUGGER,
        )

    def test_attempt_number_cannot_be_zero(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self.create_execution(attempt=0)