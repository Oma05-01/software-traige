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

from .models import AgentExecution
from .runner import run_receptionist

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