from django.test import TestCase

from apps.tickets.models import Ticket
from apps.events.models import WorkflowEvent

from .models import WorkflowRun
from .services import (
    ActiveWorkflowExists,
    TicketNotProcessable,
    InvalidWorkflowTransition,
    create_workflow_for_ticket,
    transition_workflow,
    record_workflow_event,
)


class WorkflowServiceTests(TestCase):

    def setUp(self):
        self.ticket = Ticket.objects.create(
            title="PDF upload failure",
            description="Upload crashes above 25 MB.",
            reporter_email="reporter@example.com",
        )

    def test_create_workflow(self):
        workflow = create_workflow_for_ticket(
            self.ticket.id
        )

        self.assertEqual(
            workflow.status,
            WorkflowRun.Status.QUEUED,
        )

        self.assertEqual(
            workflow.current_stage,
            WorkflowRun.Stage.RECEPTIONIST,
        )

        self.assertEqual(
            WorkflowEvent.objects.filter(
                workflow_run=workflow,
                event_type="workflow.created",
            ).count(),
            1,
        )

    def test_prevent_duplicate_active_workflows(self):
        create_workflow_for_ticket(self.ticket.id)

        with self.assertRaises(ActiveWorkflowExists):
            create_workflow_for_ticket(self.ticket.id)

        self.assertEqual(
            WorkflowRun.objects.filter(
                ticket=self.ticket
            ).count(),
            1,
        )

    def test_cannot_create_workflow_for_closed_ticket(self):
        self.ticket.status = Ticket.Status.CLOSED
        self.ticket.save(update_fields=["status"])

        with self.assertRaises(TicketNotProcessable):
            create_workflow_for_ticket(self.ticket.id)

    def test_start_workflow(self):
        workflow = create_workflow_for_ticket(
            self.ticket.id
        )

        workflow = transition_workflow(
            workflow.id,
            WorkflowRun.Status.RUNNING,
        )

        self.ticket.refresh_from_db()

        self.assertEqual(
            workflow.status,
            WorkflowRun.Status.RUNNING,
        )

        self.assertIsNotNone(workflow.started_at)

        self.assertEqual(
            self.ticket.status,
            Ticket.Status.IN_PROGRESS,
        )

    def test_transition_to_awaiting_review(self):
        workflow = create_workflow_for_ticket(
            self.ticket.id
        )

        transition_workflow(
            workflow.id,
            WorkflowRun.Status.RUNNING,
        )

        workflow = transition_workflow(
            workflow.id,
            WorkflowRun.Status.AWAITING_REVIEW,
        )

        self.ticket.refresh_from_db()

        self.assertEqual(
            workflow.status,
            WorkflowRun.Status.AWAITING_REVIEW,
        )

        self.assertEqual(
            self.ticket.status,
            Ticket.Status.AWAITING_REVIEW,
        )

    def test_rejected_workflow_returns_to_running(self):
        workflow = create_workflow_for_ticket(
            self.ticket.id
        )

        transition_workflow(
            workflow.id,
            WorkflowRun.Status.RUNNING,
        )

        transition_workflow(
            workflow.id,
            WorkflowRun.Status.AWAITING_REVIEW,
        )

        workflow = transition_workflow(
            workflow.id,
            WorkflowRun.Status.RUNNING,
            source=WorkflowEvent.Source.HUMAN,
        )

        self.ticket.refresh_from_db()

        self.assertEqual(
            workflow.status,
            WorkflowRun.Status.RUNNING,
        )

        self.assertEqual(
            self.ticket.status,
            Ticket.Status.IN_PROGRESS,
        )

    def test_complete_workflow(self):
        workflow = create_workflow_for_ticket(
            self.ticket.id
        )

        transition_workflow(
            workflow.id,
            WorkflowRun.Status.RUNNING,
        )

        transition_workflow(
            workflow.id,
            WorkflowRun.Status.AWAITING_REVIEW,
        )

        workflow = transition_workflow(
            workflow.id,
            WorkflowRun.Status.COMPLETED,
            source=WorkflowEvent.Source.HUMAN,
        )

        self.ticket.refresh_from_db()

        self.assertEqual(
            workflow.status,
            WorkflowRun.Status.COMPLETED,
        )

        self.assertIsNotNone(workflow.finished_at)

        self.assertEqual(
            self.ticket.status,
            Ticket.Status.COMPLETED,
        )

    def test_invalid_transition_is_rejected(self):
        workflow = create_workflow_for_ticket(
            self.ticket.id
        )

        with self.assertRaises(InvalidWorkflowTransition):
            transition_workflow(
                workflow.id,
                WorkflowRun.Status.COMPLETED,
            )

        workflow.refresh_from_db()
        self.ticket.refresh_from_db()

        self.assertEqual(
            workflow.status,
            WorkflowRun.Status.QUEUED,
        )

        self.assertEqual(
            self.ticket.status,
            Ticket.Status.SUBMITTED,
        )

    def test_failed_workflow_can_be_retried_with_new_run(self):
        workflow = create_workflow_for_ticket(
            self.ticket.id
        )

        transition_workflow(
            workflow.id,
            WorkflowRun.Status.FAILED,
        )

        self.assertIsNotNone(
            WorkflowRun.objects.get(pk=workflow.id).finished_at
        )

        new_workflow = create_workflow_for_ticket(
            self.ticket.id
        )

        self.assertNotEqual(
            workflow.id,
            new_workflow.id,
        )

        self.assertEqual(
            new_workflow.status,
            WorkflowRun.Status.QUEUED,
        )

    def test_custom_workflow_event(self):
        workflow = create_workflow_for_ticket(
            self.ticket.id
        )

        event = record_workflow_event(
            workflow_id=workflow.id,
            event_type="agent.started",
            source=WorkflowEvent.Source.AGENT,
            payload={
                "agent": "receptionist",
            },
        )

        self.assertEqual(
            event.event_type,
            "agent.started",
        )

        self.assertEqual(
            event.source,
            WorkflowEvent.Source.AGENT,
        )

        self.assertEqual(
            event.payload["agent"],
            "receptionist",
        )

    def test_repeated_status_transition_is_idempotent(self):
        workflow = create_workflow_for_ticket(
            self.ticket.id
        )

        transition_workflow(
            workflow.id,
            WorkflowRun.Status.RUNNING,
        )

        event_count = WorkflowEvent.objects.filter(
            workflow_run=workflow
        ).count()

        transition_workflow(
            workflow.id,
            WorkflowRun.Status.RUNNING,
        )

        self.assertEqual(
            WorkflowEvent.objects.filter(
                workflow_run=workflow
            ).count(),
            event_count,
        )