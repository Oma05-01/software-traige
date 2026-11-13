import logging
from django.conf import settings
from django.db import transaction

from apps.tickets.models import Ticket
from apps.workflow.models import WorkflowRun
from apps.agents.llm.base import LLMTransientError
from apps.workflow.services import (
    advance_workflow_stage,
    transition_workflow,
)
from apps.events.models import WorkflowEvent

from .models import AgentExecution
from .services import (
    ActiveAgentExecutionExists,
    WorkflowNotRunning,
    create_agent_execution,
    start_agent_execution,
    complete_agent_execution,
    fail_agent_execution,
    record_transient_agent_failure,
)
from apps.workflow.services import (
    advance_workflow_stage,
    transition_workflow,
    record_workflow_event,
)
from .implementations.receptionist import classify_ticket
from apps.reviews.services import create_classification_review

logger = logging.getLogger(__name__)

def get_receptionist_classifier():
    """Select the configured Receptionist implementation."""

    mode = settings.RECEPTIONIST_MODE

    if mode == "deterministic":
        return classify_ticket

    if mode == "llm":
        from .implementations.receptionist_llm import (
            classify_ticket_llm,
        )

        return classify_ticket_llm

    raise ValueError(
        f"Unsupported RECEPTIONIST_MODE: {mode}"
    )


def build_receptionist_input(ticket):
    """
    Prepare the minimum information required by the Receptionist.

    Reporter contact information is deliberately excluded.
    """

    return {
        "ticket_id": str(ticket.id),
        "title": ticket.title,
        "description": ticket.description,
        "environment": ticket.environment,
        "steps_to_reproduce": ticket.steps_to_reproduce,
        "expected_behavior": ticket.expected_behavior,
        "actual_behavior": ticket.actual_behavior,
    }


def get_or_create_receptionist_execution(workflow,redelivered=False):
    """
    Retrieve an existing Receptionist execution when possible.

    Creates a new attempt only when no existing execution
    is active or successfully completed.
    """

    latest = (
        AgentExecution.objects
        .filter(
            workflow_run=workflow,
            agent_type=AgentExecution.AgentType.RECEPTIONIST,
        )
        .order_by("-attempt")
        .first()
    )

    if latest:
        if latest.status in {
            AgentExecution.Status.SUCCEEDED,
            AgentExecution.Status.SKIPPED,
        }:
            return latest, False

        if latest.status == AgentExecution.Status.RUNNING:
            return latest, redelivered

        if latest.status == AgentExecution.Status.QUEUED:
            return latest, True

        # A failed execution can be retried.

    try:
        execution = create_agent_execution(
            workflow_id=workflow.id,
            agent_type=AgentExecution.AgentType.RECEPTIONIST,
            input_payload=build_receptionist_input(
                workflow.ticket
            ),
        )

        return execution, True

    except ActiveAgentExecutionExists:
        # Another request may have created an execution
        # between our initial lookup and creation.

        active = AgentExecution.objects.filter(
            workflow_run=workflow,
            status__in=[
                AgentExecution.Status.QUEUED,
                AgentExecution.Status.RUNNING,
            ],
        ).first()

        if (
            active
            and active.agent_type
            == AgentExecution.AgentType.RECEPTIONIST
        ):
            return (
                active,
                active.status == AgentExecution.Status.QUEUED
                or (
                    active.status == AgentExecution.Status.RUNNING
                    and redelivered
                ),
            )

        raise


def persist_receptionist_result(execution, result, claim_token=None):
    """
    Persist classification, execution output and routing
    decisions within a database transaction.
    """

    workflow_id = execution.workflow_run_id
    ticket_id = execution.workflow_run.ticket_id

    with transaction.atomic():

        # Lock order: Ticket -> WorkflowRun -> AgentExecution.
        ticket = (
            Ticket.objects
            .select_for_update()
            .get(pk=ticket_id)
        )

        if not result["needs_human_review"]:
            ticket.category = result["category"]
            ticket.priority = result["priority"]

            ticket.save(
                update_fields=[
                    "category",
                    "priority",
                    "updated_at",
                ]
            )

        completed_execution = complete_agent_execution(
            execution.id,
            output_payload=result, claim_token=claim_token,
        )

        if result["needs_human_review"]:
            create_classification_review(completed_execution.id)

        record_workflow_event(
            workflow_id=workflow_id,
            event_type="agent.classification_completed",
            source=WorkflowEvent.Source.AGENT,
            payload={
                "agent": AgentExecution.AgentType.RECEPTIONIST,
                "category": result["category"],
                "priority": result["priority"],
                "confidence": result["classification_confidence"],
                "needs_human_review": result["needs_human_review"],
            },
        )

        if result["needs_human_review"]:

            # Uncertain classifications must not be routed
            # automatically to another agent.
            transition_workflow(
                workflow_id,
                WorkflowRun.Status.AWAITING_REVIEW,
                source=WorkflowEvent.Source.AGENT,
            )

            advance_workflow_stage(
                workflow_id,
                WorkflowRun.Stage.HUMAN_REVIEW,
                source=WorkflowEvent.Source.AGENT,
            )

        else:

            next_stage = {
                Ticket.Category.BUG:
                    WorkflowRun.Stage.DEBUGGER,

                Ticket.Category.FEATURE:
                    WorkflowRun.Stage.PRODUCT_MANAGER,
            }.get(result["category"])

            if next_stage is None:
                raise ValueError(
                    "Classification cannot be routed automatically."
                )

            advance_workflow_stage(
                workflow_id,
                next_stage,
                source=WorkflowEvent.Source.AGENT,
            )

    return completed_execution


def run_receptionist(workflow_id, celery_task_id=None, redelivered=False):
    """
    Execute the Receptionist against a running workflow.

    This is a synchronous execution for now.
    It will later become the body of a Celery task.
    """

    workflow = (
        WorkflowRun.objects
        .select_related("ticket")
        .get(pk=workflow_id)
    )

    # Check for previously completed execution before
    # rejecting a repeated invocation.
    latest = (
        AgentExecution.objects
        .filter(
            workflow_run=workflow,
            agent_type=AgentExecution.AgentType.RECEPTIONIST,
        )
        .order_by("-attempt")
        .first()
    )

    if latest and latest.status in {
        AgentExecution.Status.SUCCEEDED,
        AgentExecution.Status.SKIPPED,
    }:
        return latest

    if workflow.status != WorkflowRun.Status.RUNNING:
        raise WorkflowNotRunning(
            "The Receptionist requires a running workflow."
        )

    execution, should_start = get_or_create_receptionist_execution(
        workflow,
        redelivered=redelivered,
    )

    if not should_start:
        return execution

    execution, claimed = start_agent_execution(
        execution.id,
        celery_task_id=celery_task_id,
        redelivered=redelivered,
    )

    # Another worker or request already claimed execution.
    if not claimed:
        return execution

    try:
        classifier = get_receptionist_classifier()

        result = classifier(workflow.ticket)

        return persist_receptionist_result(
            execution,
            result,
            claim_token=execution.claim_token,
        )

    except LLMTransientError:
        logger.exception(
            "Receptionist encountered a transient LLM failure "
            "for workflow %s.",
            workflow_id,
        )

        try:
            record_transient_agent_failure(
                execution.id,
                claim_token=execution.claim_token,
            )

        except Exception:
            logger.exception(
                "Could not persist transient Receptionist failure "
                "for execution %s.",
                execution.id,
            )
            raise

        raise

    except Exception:
        logger.exception(
            "Receptionist execution failed for workflow %s",
            workflow_id,
        )

        try:
            fail_agent_execution(
                execution.id,
                error_code="RECEPTIONIST_EXECUTION_FAILED",
                error_message=(
                    "Receptionist processing failed. "
                    "Check application logs for details."
                ),
                claim_token=execution.claim_token,
                fail_workflow=True,
                workflow_failure_source=WorkflowEvent.Source.AGENT,
            )

        except Exception:
            logger.exception(
                "Could not complete Receptionist failure "
                "handling for execution %s",
                execution.id,
            )

        raise
