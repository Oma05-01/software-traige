import logging
from apps.reviews.services import create_review_request
from django.db import transaction

from apps.agents.implementations.support_rep import (
    draft_support_response,
)
from apps.agents.models import AgentExecution
from apps.agents.services import (
    ActiveAgentExecutionExists,
    complete_agent_execution,
    create_agent_execution,
    fail_agent_execution,
    start_agent_execution,
)
from apps.events.models import WorkflowEvent
from apps.workflow.models import WorkflowRun
from apps.workflow.services import (
    advance_workflow_stage,
    record_workflow_event,
    transition_workflow,
)


logger = logging.getLogger(__name__)


class SupportRepNotReady(Exception):
    """Raised when the Support Rep's prerequisites are not satisfied."""


def build_support_rep_input(
    ticket,
    receptionist_findings,
    debugger_findings,
):
    """
    Build a privacy-conscious snapshot of the information
    the Support Rep needs.

    Reporter email and other unnecessary personal information
    are deliberately excluded.
    """

    return {
        "ticket_id": str(ticket.id),
        "title": ticket.title,
        "reporter_name": ticket.reporter_name,
        "description": ticket.description,
        "environment": ticket.environment,
        "steps_to_reproduce": ticket.steps_to_reproduce,
        "expected_behavior": ticket.expected_behavior,
        "actual_behavior": ticket.actual_behavior,
        "receptionist_findings": receptionist_findings,
        "debugger_findings": debugger_findings,
    }


def get_receptionist_output(workflow):
    """Retrieve the latest successful Receptionist result."""

    execution = AgentExecution.objects.filter(
        workflow_run=workflow,
        agent_type="receptionist",
        status=AgentExecution.Status.SUCCEEDED,
    ).order_by("-attempt", "-created_at").first()

    if execution is None:
        raise SupportRepNotReady(
            "A successful Receptionist execution is required."
        )

    if not isinstance(execution.output_payload, dict):
        raise SupportRepNotReady(
            "The Receptionist output is missing or invalid."
        )

    return execution.output_payload


def get_debugger_output(workflow):
    """
    Retrieve the latest successful Debugger result.

    A successful investigation with no relevant evidence is
    still a valid result for Support Rep drafting.
    """

    execution = AgentExecution.objects.filter(
        workflow_run=workflow,
        agent_type="debugger",
        status=AgentExecution.Status.SUCCEEDED,
    ).order_by("-attempt", "-created_at").first()

    if execution is None:
        raise SupportRepNotReady(
            "A successful Debugger execution is required."
        )

    if not isinstance(execution.output_payload, dict):
        raise SupportRepNotReady(
            "The Debugger output is missing or invalid."
        )

    return execution.output_payload


def get_or_create_support_rep_execution(workflow):
    """
    Return an existing successful or active Support Rep execution,
    or create the next attempt.

    Failed executions may be retried as a new attempt.
    """

    receptionist_output = get_receptionist_output(workflow)
    debugger_output = get_debugger_output(workflow)

    existing_success = AgentExecution.objects.filter(
        workflow_run=workflow,
        agent_type="support_rep",
        status=AgentExecution.Status.SUCCEEDED,
    ).order_by("-attempt").first()

    if existing_success is not None:
        return existing_success

    active_execution = AgentExecution.objects.filter(
        workflow_run=workflow,
        status__in=[
            AgentExecution.Status.QUEUED,
            AgentExecution.Status.RUNNING,
        ],
    ).order_by("-attempt").first()

    if active_execution is not None:

        if active_execution.agent_type != "support_rep":
            raise SupportRepNotReady(
                "Another agent execution is currently active."
            )

        return active_execution

    input_payload = build_support_rep_input(
        workflow.ticket,
        receptionist_output,
        debugger_output,
    )

    try:
        return create_agent_execution(
            workflow.id,
            "support_rep",
            input_payload,
        )

    except ActiveAgentExecutionExists:
        # Another task may have created the execution between
        # our initial check and the database insert.
        active_execution = AgentExecution.objects.filter(
            workflow_run=workflow,
            status__in=[
                AgentExecution.Status.QUEUED,
                AgentExecution.Status.RUNNING,
            ],
        ).order_by("-attempt").first()

        if (
            active_execution is not None
            and active_execution.agent_type == "support_rep"
        ):
            return active_execution

        raise


@transaction.atomic
def persist_support_response(execution, result):
    """
    Complete the Support Rep execution, record the draft event,
    advance to Human Review, and move the workflow to awaiting_review.

    The entire persistence operation is atomic.
    """

    if not isinstance(result, dict):
        raise TypeError("Support Rep result must be a dictionary.")

    current_execution = AgentExecution.objects.get(
        pk=execution.pk,
    )

    # Protect against duplicate calls after successful completion.
    if current_execution.status == AgentExecution.Status.SUCCEEDED:
        return current_execution

    workflow = current_execution.workflow_run

    if workflow.status != WorkflowRun.Status.RUNNING:
        raise SupportRepNotReady(
            "The workflow is no longer running."
        )

    if workflow.current_stage != WorkflowRun.Stage.SUPPORT_REP:
        raise SupportRepNotReady(
            "The workflow is not currently at the Support Rep stage."
        )

    if result.get("draft_status") != "pending_human_review":
        raise ValueError(
            "The Support Rep must produce a draft for human review."
        )

    if result.get("external_send_authorized") is not False:
        raise ValueError(
            "The Support Rep must not authorize external message delivery."
        )

    completed_execution = complete_agent_execution(
        current_execution.id,
        result,
    )

    review_request = create_review_request(
        completed_execution.id,
    )

    record_workflow_event(
        workflow.id,
        event_type="support.response_drafted",
        source=WorkflowEvent.Source.AGENT,
        payload={
            "agent_execution_id": str(completed_execution.id),
            "review_request_id": str(review_request.id),
            "draft_status": result["draft_status"],
            "response_type": result.get("response_type"),
            "evidence_reference_count": len(
                result.get("evidence_references", [])
            ),
            "follow_up_question_count": len(
                result.get("follow_up_questions", [])
            ),
            "requires_human_review": True,
            "external_send_authorized": False,
        },
    )

    # SUPPORT_REP -> HUMAN_REVIEW
    advance_workflow_stage(
        workflow.id,
        WorkflowRun.Stage.HUMAN_REVIEW,
    )

    # RUNNING -> AWAITING_REVIEW
    transition_workflow(
        workflow.id,
        WorkflowRun.Status.AWAITING_REVIEW,
    )

    return completed_execution


def run_support_rep(workflow_id, celery_task_id=None):
    """
    Execute the Support Rep for a workflow at the Support Rep stage.

    The result is a draft only. No external communication is sent.
    """

    workflow = WorkflowRun.objects.select_related("ticket").get(
        pk=workflow_id,
    )

    # An already completed execution makes duplicate delivery safe.
    existing_success = AgentExecution.objects.filter(
        workflow_run=workflow,
        agent_type="support_rep",
        status=AgentExecution.Status.SUCCEEDED,
    ).order_by("-attempt").first()

    if existing_success is not None:
        return existing_success

    if workflow.status != WorkflowRun.Status.RUNNING:
        raise SupportRepNotReady(
            "The workflow must be running before Support Rep execution."
        )

    if workflow.current_stage != WorkflowRun.Stage.SUPPORT_REP:
        raise SupportRepNotReady(
            "The workflow must be at the Support Rep stage."
        )

    execution = None

    try:
        execution = get_or_create_support_rep_execution(workflow)

        execution, should_execute = start_agent_execution(
            execution.id,
            celery_task_id=celery_task_id,
        )

        # Another delivery may already have started this execution.
        if not should_execute:
            return execution

        receptionist_output = get_receptionist_output(workflow)
        debugger_output = get_debugger_output(workflow)

        result = draft_support_response(
            workflow.ticket,
            receptionist_output,
            debugger_output,
        )

        completed_execution = persist_support_response(
            execution,
            result,
        )

        logger.info(
            "Support Rep completed for workflow %s; "
            "draft is awaiting human review.",
            workflow.id,
        )

        return completed_execution

    except Exception as exc:

        logger.exception(
            "Support Rep execution failed for workflow %s",
            workflow.id,
        )

        if execution is not None:
            # Follow the workflow lock order used by the other runners.
            try:
                current_workflow = WorkflowRun.objects.get(
                    pk=workflow.id,
                )

                if current_workflow.status in (
                    WorkflowRun.Status.QUEUED,
                    WorkflowRun.Status.RUNNING,
                ):
                    transition_workflow(
                        workflow.id,
                        WorkflowRun.Status.FAILED,
                    )

            except Exception:
                logger.exception(
                    "Could not mark workflow %s as failed.",
                    workflow.id,
                )

            try:
                fail_agent_execution(
                    execution.id,
                    error_code=type(exc).__name__,
                    error_message=str(exc),
                )

            except Exception:
                logger.exception(
                    "Could not mark Support Rep execution %s as failed.",
                    execution.id,
                )

        raise