import logging

from django.db import transaction
from apps.agents.llm.base import LLMTransientError
from apps.tickets.models import Ticket
from apps.workflow.models import WorkflowRun
from apps.workflow.services import (
    advance_workflow_stage,
    transition_workflow,
    record_workflow_event,
)
from apps.events.models import WorkflowEvent

from apps.agents.models import AgentExecution
from apps.agents.services import (
    ActiveAgentExecutionExists,
    WorkflowNotRunning,
    create_agent_execution,
    start_agent_execution,
    complete_agent_execution,
    fail_agent_execution,
    record_transient_agent_failure,
)

from apps.agents.implementations.product_manager import (
    assess_feature_request,
)


logger = logging.getLogger(__name__)


class ProductManagerNotReady(Exception):
    """Raised when the Product Manager cannot execute its task."""


def build_product_manager_input(ticket, receptionist_findings):
    """
    Prepare the Product Manager input.

    Reporter contact information is deliberately excluded.
    """

    return {
        "title": ticket.title,
        "description": ticket.description,
        "environment": ticket.environment,
        "steps_to_reproduce": ticket.steps_to_reproduce,
        "expected_behavior": ticket.expected_behavior,
        "actual_behavior": ticket.actual_behavior,
        "receptionist_findings": receptionist_findings,
    }


def get_receptionist_output(workflow):
    """Retrieve the latest successful Receptionist execution."""

    execution = AgentExecution.objects.filter(
        workflow_run=workflow,
        agent_type=AgentExecution.AgentType.RECEPTIONIST,
        status=AgentExecution.Status.SUCCEEDED,
    ).order_by("-attempt").first()

    if execution is None:
        raise ProductManagerNotReady(
            "A successful Receptionist execution is required."
        )

    if not isinstance(execution.output_payload, dict):
        raise ProductManagerNotReady(
            "Receptionist output is missing or invalid."
        )

    return execution.output_payload

def get_effective_receptionist_output(workflow):
    """
    Combine the original Receptionist findings with the
    ticket's authoritative, staff-confirmed classification.

    The original AgentExecution payload remains unchanged.
    """

    receptionist_output = get_receptionist_output(workflow)

    # Read the authoritative classification directly from the DB.
    ticket = Ticket.objects.only(
        "category",
        "priority",
    ).get(pk=workflow.ticket_id)

    return {
        **receptionist_output,
        "category": ticket.category,
        "priority": ticket.priority,
    }

def get_or_create_product_manager_execution(workflow):
    """Retrieve or create a Product Manager execution."""

    receptionist_output = get_effective_receptionist_output(workflow)

    latest = AgentExecution.objects.filter(
        workflow_run=workflow,
        agent_type=AgentExecution.AgentType.PRODUCT_MANAGER,
    ).order_by("-attempt").first()

    if latest:
        if latest.status in {
            AgentExecution.Status.SUCCEEDED,
            AgentExecution.Status.SKIPPED,
            AgentExecution.Status.RUNNING,
        }:
            return latest, False

        if latest.status == AgentExecution.Status.QUEUED:
            return latest, True

        # Failed executions may be retried.

    try:
        execution = create_agent_execution(
            workflow_id=workflow.id,
            agent_type=AgentExecution.AgentType.PRODUCT_MANAGER,
            input_payload=build_product_manager_input(
                workflow.ticket,
                receptionist_output,
            ),
        )

        return execution, True

    except ActiveAgentExecutionExists:
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
            == AgentExecution.AgentType.PRODUCT_MANAGER
        ):
            return (
                active,
                active.status == AgentExecution.Status.QUEUED,
            )

        raise


@transaction.atomic
def persist_product_manager_result(execution, result):
    """
    Persist the assessment and advance to Support Rep.

    Execution completion, event recording and stage advancement
    happen together.
    """

    if not isinstance(result, dict):
        raise TypeError(
            "Product Manager result must be a dictionary."
        )

    if result.get("assessment_status") != "pending_human_review":
        raise ValueError(
            "Product Manager must produce an assessment for review."
        )

    if result.get("requires_human_review") is not True:
        raise ValueError(
            "Product Manager assessments must require human review."
        )

    if result.get("approval_status") != "not_approved":
        raise ValueError(
            "Product Manager cannot approve its own assessment."
        )

    workflow_id = execution.workflow_run_id
    ticket_id = execution.workflow_run.ticket_id

    # Maintain lock order: Ticket -> Workflow -> Execution.
    Ticket.objects.select_for_update().get(pk=ticket_id)

    workflow = WorkflowRun.objects.get(pk=workflow_id)

    if workflow.status != WorkflowRun.Status.RUNNING:
        raise ProductManagerNotReady(
            "The workflow is no longer running."
        )

    if workflow.current_stage != WorkflowRun.Stage.PRODUCT_MANAGER:
        raise ProductManagerNotReady(
            "The workflow is not at the Product Manager stage."
        )

    completed_execution = complete_agent_execution(
        execution.id,
        output_payload=result,
    )

    record_workflow_event(
        workflow_id=workflow_id,
        event_type="agent.feature_assessment_completed",
        source=WorkflowEvent.Source.AGENT,
        payload={
            "agent": AgentExecution.AgentType.PRODUCT_MANAGER,
            "assessment_confidence": result["assessment_confidence"],
            "acceptance_criteria_count": len(
                result["acceptance_criteria"]
            ),
            "consideration_count": len(
                result["considerations"]
            ),
            "open_question_count": len(
                result["open_questions"]
            ),
            "requires_human_review": True,
            "approval_status": "not_approved",
        },
    )

    # PRODUCT_MANAGER -> SUPPORT_REP
    advance_workflow_stage(
        workflow_id,
        WorkflowRun.Stage.SUPPORT_REP,
        source=WorkflowEvent.Source.AGENT,
    )

    return completed_execution



def run_product_manager(workflow_id, celery_task_id=None):
    """Execute the Product Manager for a running feature workflow."""

    workflow = WorkflowRun.objects.select_related("ticket").get(
        pk=workflow_id
    )

    latest = AgentExecution.objects.filter(
        workflow_run=workflow,
        agent_type=AgentExecution.AgentType.PRODUCT_MANAGER,
    ).order_by("-attempt").first()

    if latest and latest.status in {
        AgentExecution.Status.SUCCEEDED,
        AgentExecution.Status.SKIPPED,
    }:
        return latest

    if workflow.status != WorkflowRun.Status.RUNNING:
        raise WorkflowNotRunning(
            "The Product Manager requires a running workflow."
        )

    if workflow.current_stage != WorkflowRun.Stage.PRODUCT_MANAGER:
        raise ProductManagerNotReady(
            "The workflow is not currently assigned to Product Manager."
        )

    if workflow.ticket.category != Ticket.Category.FEATURE:
        raise ProductManagerNotReady(
            "The Product Manager only processes feature requests."
        )

    execution, should_start = (
        get_or_create_product_manager_execution(workflow)
    )

    if not should_start:
        return execution

    execution, claimed = start_agent_execution(
        execution.id,
        celery_task_id=celery_task_id,
    )

    if not claimed:
        return execution

    try:
        receptionist_output = get_effective_receptionist_output(workflow)

        result = assess_feature_request(
            workflow.ticket,
            receptionist_output,
        )

        completed_execution = persist_product_manager_result(
            execution,
            result,
        )

        logger.info(
            "Product Manager completed for workflow %s.",
            workflow.id,
        )

        return completed_execution

    except LLMTransientError:
        logger.exception(
            "Product Manager encountered a transient LLM failure "
            "for workflow %s.",
            workflow_id,
        )

        try:
            record_transient_agent_failure(execution.id)

        except Exception:
            logger.exception(
                "Could not persist transient Product Manager failure "
                "for execution %s.",
                execution.id,
            )
            raise

        raise

    except Exception:
        logger.exception(
            "Product Manager execution failed for workflow %s",
            workflow_id,
        )

        try:
            current_workflow = WorkflowRun.objects.get(
                pk=workflow_id
            )

            if current_workflow.status == WorkflowRun.Status.RUNNING:
                transition_workflow(
                    workflow_id,
                    WorkflowRun.Status.FAILED,
                    source=WorkflowEvent.Source.AGENT,
                )

            fail_agent_execution(
                execution.id,
                error_code="PRODUCT_MANAGER_EXECUTION_FAILED",
                error_message=(
                    "Product Manager processing failed. "
                    "Check application logs for details."
                ),
            )

        except Exception:
            logger.exception(
                "Could not persist Product Manager failure "
                "for execution %s",
                execution.id,
            )

        raise
