import logging
from django.conf import settings
from django.db import transaction
from .implementations.debugger import investigate_ticket
from apps.tickets.models import Ticket
from apps.workflow.models import WorkflowRun
from apps.agents.llm.base import LLMTransientError
from apps.workflow.services import (
    advance_workflow_stage,
    transition_workflow,
    record_workflow_event,
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

from .implementations.debugger import investigate_ticket


logger = logging.getLogger(__name__)


class DebuggerNotReady(Exception):
    """Raised when the Debugger cannot execute its assigned task."""


def get_debugger_investigator():
    """
    Select the Debugger implementation from project settings.

    Deterministic mode remains the default.
    """

    mode = getattr(
        settings,
        "DEBUGGER_MODE",
        "deterministic",
    ).lower()

    if mode == "deterministic":
        return investigate_ticket

    if mode == "llm":
        from .implementations.debugger_llm import (
            investigate_ticket_llm,
        )

        return investigate_ticket_llm

    raise DebuggerNotReady(
        f"Unsupported DEBUGGER_MODE: {mode}"
    )

def build_debugger_input(ticket, receptionist_output):
    """
    Prepare the information required by the Debugger.

    Reporter contact details are deliberately excluded.
    """

    return {
        "ticket_id": str(ticket.id),
        "title": ticket.title,
        "description": ticket.description,
        "environment": ticket.environment,
        "steps_to_reproduce": ticket.steps_to_reproduce,
        "expected_behavior": ticket.expected_behavior,
        "actual_behavior": ticket.actual_behavior,
        "receptionist_findings": receptionist_output,
    }


def get_or_create_debugger_execution(workflow):
    """
    Retrieve an existing Debugger execution where possible.

    Creates a new attempt if the previous execution failed.
    """

    latest = (
        AgentExecution.objects
        .filter(
            workflow_run=workflow,
            agent_type=AgentExecution.AgentType.DEBUGGER,
        )
        .order_by("-attempt")
        .first()
    )

    if latest:
        if latest.status in {
            AgentExecution.Status.SUCCEEDED,
            AgentExecution.Status.SKIPPED,
            AgentExecution.Status.RUNNING,
        }:
            return latest, False

        if latest.status == AgentExecution.Status.QUEUED:
            return latest, True

        # A failed execution can be retried.

    try:
        execution = create_agent_execution(
            workflow_id=workflow.id,
            agent_type=AgentExecution.AgentType.DEBUGGER,
            input_payload=build_debugger_input(
                workflow.ticket,
                get_receptionist_output(workflow),
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
            == AgentExecution.AgentType.DEBUGGER
        ):
            return (
                active,
                active.status == AgentExecution.Status.QUEUED,
            )

        raise


def get_receptionist_output(workflow):
    """
    Retrieve the latest successful Receptionist output.
    """

    execution = (
        AgentExecution.objects
        .filter(
            workflow_run=workflow,
            agent_type=AgentExecution.AgentType.RECEPTIONIST,
            status=AgentExecution.Status.SUCCEEDED,
        )
        .order_by("-attempt")
        .first()
    )

    if execution is None:
        raise DebuggerNotReady(
            "The Receptionist must complete successfully "
            "before the Debugger can execute."
        )

    return execution.output_payload


@transaction.atomic
def persist_debugger_result(execution, result):
    """
    Persist investigation output and advance the workflow.

    Agent completion, event creation and stage advancement
    are committed together.
    """

    workflow_id = execution.workflow_run_id
    ticket_id = execution.workflow_run.ticket_id

    # Maintain lock order: Ticket -> WorkflowRun -> Execution.
    Ticket.objects.select_for_update().get(
        pk=ticket_id
    )

    completed_execution = complete_agent_execution(
        execution.id,
        output_payload=result,
    )

    record_workflow_event(
        workflow_id=workflow_id,
        event_type="agent.investigation_completed",
        source=WorkflowEvent.Source.AGENT,
        payload={
            "agent": AgentExecution.AgentType.DEBUGGER,
            "investigation_status": result["investigation_status"],
            "evidence_count": result["retrieval_metadata"]["evidence_count"],
            "root_cause_status": result["root_cause"]["status"],
        },
    )

    # Even when no evidence is found, Support Rep can
    # prepare a transparent response explaining the limitation.
    advance_workflow_stage(
        workflow_id,
        WorkflowRun.Stage.SUPPORT_REP,
        source=WorkflowEvent.Source.AGENT,
    )

    return completed_execution



def run_debugger(workflow_id, celery_task_id=None):
    """
    Execute the Debugger against a running workflow.

    Currently synchronous. Later, Celery will call this
    same function from an independent worker.
    """

    workflow = (
        WorkflowRun.objects
        .select_related("ticket")
        .get(pk=workflow_id)
    )

    # Repeated invocation after successful completion
    # must not produce another investigation.
    latest = (
        AgentExecution.objects
        .filter(
            workflow_run=workflow,
            agent_type=AgentExecution.AgentType.DEBUGGER,
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
            "The Debugger requires a running workflow."
        )

    if workflow.current_stage != WorkflowRun.Stage.DEBUGGER:
        raise DebuggerNotReady(
            "The workflow is not currently assigned to the Debugger."
        )

    if workflow.ticket.category != Ticket.Category.BUG:
        raise DebuggerNotReady(
            "The Debugger only processes bug reports."
        )

    execution, should_start = (
        get_or_create_debugger_execution(workflow)
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
        receptionist_findings = get_receptionist_output(workflow)

        investigator = get_debugger_investigator()

        result = investigator(
            workflow.ticket,
            receptionist_findings=receptionist_findings,
        )

        return persist_debugger_result(
            execution,
            result,
        )

    except LLMTransientError:
        logger.exception(
            "Debugger encountered a transient LLM failure "
            "for workflow %s.",
            workflow_id,
        )

        try:
            record_transient_agent_failure(execution.id)

        except Exception:
            logger.exception(
                "Could not persist transient Debugger failure "
                "for execution %s.",
                execution.id,
            )
            raise

        raise

    except Exception:
        logger.exception(
            "Debugger execution failed for workflow %s",
            workflow_id,
        )

        try:
            # Fail the workflow before the execution so that
            # database locks are acquired consistently:
            # Ticket -> WorkflowRun -> AgentExecution.
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
                error_code="DEBUGGER_EXECUTION_FAILED",
                error_message=(
                    "Debugger processing failed. "
                    "Check application logs for details."
                ),
            )

        except Exception:
            logger.exception(
                "Could not persist Debugger failure "
                "for execution %s",
                execution.id,
            )

        raise
