from django.db import transaction
from django.utils import timezone
import logging
from apps.tickets.models import Ticket
from apps.tickets.services import transition_ticket
from apps.events.models import WorkflowEvent

from .models import ACTIVE_WORKFLOW_STATUSES, WorkflowRun

logger = logging.getLogger(__name__)


class ActiveWorkflowExists(Exception):
    """Raised when a ticket already has an active workflow."""

    def __init__(self, workflow_id):
        self.workflow_id = workflow_id

        super().__init__(
            f"Ticket already has active workflow {workflow_id}."
        )


class TicketNotProcessable(Exception):
    """Raised when a ticket cannot start another workflow."""


class InvalidWorkflowTransition(Exception):
    """Raised when a workflow status transition is invalid."""


ALLOWED_WORKFLOW_TRANSITIONS = {
    WorkflowRun.Status.QUEUED: {
        WorkflowRun.Status.RUNNING,
        WorkflowRun.Status.FAILED,
    },

    WorkflowRun.Status.RUNNING: {
        WorkflowRun.Status.AWAITING_REVIEW,
        WorkflowRun.Status.FAILED,
    },

    WorkflowRun.Status.AWAITING_REVIEW: {
        WorkflowRun.Status.RUNNING,
        WorkflowRun.Status.COMPLETED,
        WorkflowRun.Status.FAILED,
    },

    WorkflowRun.Status.COMPLETED: set(),

    WorkflowRun.Status.FAILED: set(),
}


def _record_event(workflow, event_type, source, payload=None):
    """Internal helper for recording workflow events."""

    return WorkflowEvent.objects.create(
        workflow_run=workflow,
        event_type=event_type,
        source=source,
        payload=payload or {},
    )


@transaction.atomic
def create_workflow_for_ticket(ticket_id):
    """
    Creates a workflow for a ticket.

    Only one active workflow is permitted per ticket.
    """

    ticket = (
        Ticket.objects
        .select_for_update()
        .get(pk=ticket_id)
    )

    if ticket.status in {
        Ticket.Status.COMPLETED,
        Ticket.Status.CLOSED,
    }:
        raise TicketNotProcessable(
            f"Cannot process a ticket with status {ticket.status}."
        )

    existing = WorkflowRun.objects.filter(
        ticket=ticket,
        status__in=ACTIVE_WORKFLOW_STATUSES,
    ).first()

    if existing:
        raise ActiveWorkflowExists(existing.id)

    workflow = WorkflowRun.objects.create(
        ticket=ticket,
    )

    _record_event(
        workflow=workflow,
        event_type="workflow.created",
        source=WorkflowEvent.Source.SYSTEM,
        payload={
            "ticket_id": str(ticket.id),
            "status": workflow.status,
            "current_stage": workflow.current_stage,
            "workflow_version": workflow.workflow_version,
        },
    )

    return workflow


@transaction.atomic
def transition_workflow(
    workflow_id,
    new_status,
    source=WorkflowEvent.Source.SYSTEM,
):
    """
    Safely transitions a workflow and synchronizes
    its associated ticket status.
    """

    if new_status not in WorkflowRun.Status.values:
        raise ValueError(
            f"Unknown workflow status: {new_status}"
        )

    # Obtain the ticket ID first so all operations
    # acquire database locks in the same order.
    ticket_id = WorkflowRun.objects.values_list(
        "ticket_id",
        flat=True,
    ).get(pk=workflow_id)

    ticket = (
        Ticket.objects
        .select_for_update()
        .get(pk=ticket_id)
    )

    workflow = (
        WorkflowRun.objects
        .select_for_update()
        .get(pk=workflow_id)
    )

    current_status = workflow.status

    # Repeated requests are idempotent.
    if current_status == new_status:
        return workflow

    allowed = ALLOWED_WORKFLOW_TRANSITIONS[current_status]

    if new_status not in allowed:
        raise InvalidWorkflowTransition(
            f"Cannot transition workflow from "
            f"{current_status} to {new_status}."
        )

    # Synchronize ticket lifecycle.
    ticket_status_mapping = {
        WorkflowRun.Status.RUNNING:
            Ticket.Status.IN_PROGRESS,

        WorkflowRun.Status.AWAITING_REVIEW:
            Ticket.Status.AWAITING_REVIEW,

        WorkflowRun.Status.COMPLETED:
            Ticket.Status.COMPLETED,
    }

    target_ticket_status = ticket_status_mapping.get(
        new_status
    )

    if target_ticket_status is not None:

        # A ticket must enter IN_PROGRESS before
        # it can enter AWAITING_REVIEW.
        #
        # This also reconciles an existing mismatch
        # between workflow and ticket status.

        if (
            target_ticket_status == Ticket.Status.AWAITING_REVIEW
            and ticket.status == Ticket.Status.SUBMITTED
        ):
            transition_ticket(
                ticket.id,
                Ticket.Status.IN_PROGRESS,
            )

        transition_ticket(
            ticket.id,
            target_ticket_status,
        )

    # Update workflow timestamps.
    now = timezone.now()

    workflow.status = new_status

    if new_status == WorkflowRun.Status.RUNNING:
        if workflow.started_at is None:
            workflow.started_at = now

        workflow.finished_at = None

    elif new_status in {
        WorkflowRun.Status.COMPLETED,
        WorkflowRun.Status.FAILED,
    }:
        workflow.finished_at = now

    workflow.save(
        update_fields=[
            "status",
            "started_at",
            "finished_at",
            "updated_at",
        ]
    )

    # Persist the transition event.
    _record_event(
        workflow=workflow,
        event_type="workflow.status_changed",
        source=source,
        payload={
            "previous_status": current_status,
            "new_status": new_status,
            "ticket_id": str(ticket.id),
        },
    )

    return workflow


@transaction.atomic
def record_workflow_event(
    workflow_id,
    event_type,
    payload=None,
    source=WorkflowEvent.Source.SYSTEM,
):
    """
    Records an event associated with a workflow.
    """

    if not event_type or not event_type.strip():
        raise ValueError("Event type cannot be empty.")

    if not isinstance(payload if payload is not None else {}, dict):
        raise TypeError("Event payload must be a dictionary.")

    if source not in WorkflowEvent.Source.values:
        raise ValueError(f"Invalid event source: {source}")

    workflow = WorkflowRun.objects.get(pk=workflow_id)

    return _record_event(
        workflow=workflow,
        event_type=event_type,
        source=source,
        payload=payload,
    )

ALLOWED_STAGE_TRANSITIONS = {
    WorkflowRun.Stage.RECEPTIONIST: {
        WorkflowRun.Stage.DEBUGGER,
        WorkflowRun.Stage.PRODUCT_MANAGER,
        WorkflowRun.Stage.HUMAN_REVIEW,
    },

    WorkflowRun.Stage.DEBUGGER: {
        WorkflowRun.Stage.SUPPORT_REP,
        WorkflowRun.Stage.HUMAN_REVIEW,
    },

    WorkflowRun.Stage.PRODUCT_MANAGER: {
        WorkflowRun.Stage.SUPPORT_REP,
        WorkflowRun.Stage.HUMAN_REVIEW,
    },

    WorkflowRun.Stage.SUPPORT_REP: {
        WorkflowRun.Stage.HUMAN_REVIEW,
    },

    WorkflowRun.Stage.HUMAN_REVIEW: {
        WorkflowRun.Stage.RECEPTIONIST,
        WorkflowRun.Stage.SUPPORT_REP,
        WorkflowRun.Stage.DEBUGGER,
        WorkflowRun.Stage.PRODUCT_MANAGER,
    },
}


class InvalidWorkflowStageTransition(Exception):
    """Raised when a workflow stage transition is invalid."""


@transaction.atomic
def advance_workflow_stage(
    workflow_id,
    new_stage,
    source=WorkflowEvent.Source.SYSTEM,
):
    """Safely advances a workflow to its next stage."""

    if new_stage not in WorkflowRun.Stage.values:
        raise ValueError(f"Unknown workflow stage: {new_stage}")

    workflow = (
        WorkflowRun.objects
        .select_for_update()
        .get(pk=workflow_id)
    )

    current_stage = workflow.current_stage

    if current_stage == new_stage:
        return workflow

    allowed = ALLOWED_STAGE_TRANSITIONS[current_stage]

    if new_stage not in allowed:
        raise InvalidWorkflowStageTransition(
            f"Cannot transition workflow from "
            f"{current_stage} to {new_stage}."
        )

    workflow.current_stage = new_stage

    workflow.save(
        update_fields=["current_stage", "updated_at"]
    )

    WorkflowEvent.objects.create(
        workflow_run=workflow,
        event_type="workflow.stage_changed",
        source=source,
        payload={
            "previous_stage": current_stage,
            "new_stage": new_stage,
        },
    )

    return workflow


@transaction.atomic
def start_ticket_workflow(ticket_id):
    """
    Creates a queued workflow and schedules
    Receptionist execution after transaction commit.
    """

    workflow = create_workflow_for_ticket(ticket_id)

    workflow_id = str(workflow.id)

    def enqueue_workflow():
        try:
            # Local import avoids circular dependencies.
            from apps.agents.tasks import process_ticket_workflow

            process_ticket_workflow.delay(workflow_id)

            logger.info(
                "Workflow %s successfully queued",
                workflow_id,
            )

        except Exception as exc:
            logger.exception(
                "Failed to queue workflow %s",
                workflow_id,
            )

            # Keep the workflow queued so that it can
            # be recovered by a future dispatch mechanism.
            WorkflowEvent.objects.create(
                workflow_run_id=workflow_id,
                event_type="workflow.dispatch_failed",
                source=WorkflowEvent.Source.SYSTEM,
                payload={
                    "error_type": type(exc).__name__,
                },
            )

    transaction.on_commit(enqueue_workflow)

    return workflow
