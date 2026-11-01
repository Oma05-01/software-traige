from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from apps.workflow.models import WorkflowRun
from apps.events.models import WorkflowEvent

from .models import AgentExecution


class ActiveAgentExecutionExists(Exception):
    """Raised when a workflow already has an active agent execution."""


class WorkflowNotRunning(Exception):
    """Raised when an agent is assigned to an inactive workflow."""


class InvalidAgentExecutionTransition(Exception):
    """Raised when an agent execution transition is invalid."""


# Associate each agent with its workflow stage.
AGENT_STAGE_MAPPING = {
    AgentExecution.AgentType.RECEPTIONIST:
        WorkflowRun.Stage.RECEPTIONIST,

    AgentExecution.AgentType.DEBUGGER:
        WorkflowRun.Stage.DEBUGGER,

    AgentExecution.AgentType.PRODUCT_MANAGER:
        WorkflowRun.Stage.PRODUCT_MANAGER,

    AgentExecution.AgentType.SUPPORT_REP:
        WorkflowRun.Stage.SUPPORT_REP,
}


def _record_agent_event(
    execution,
    event_type,
    payload=None,
    source=WorkflowEvent.Source.AGENT,
):
    """Internal helper for recording agent activity."""

    return WorkflowEvent.objects.create(
        workflow_run=execution.workflow_run,
        event_type=event_type,
        source=source,
        payload={
            "execution_id": str(execution.id),
            "agent": execution.agent_type,
            "attempt": execution.attempt,
            **(payload or {}),
        },
    )


@transaction.atomic
def create_agent_execution(
    workflow_id,
    agent_type,
    input_payload=None,
):
    """
    Assigns an agent to a running workflow.

    Creates a new execution attempt and records
    the assignment as a workflow event.
    """

    if agent_type not in AgentExecution.AgentType.values:
        raise ValueError(
            f"Unknown agent type: {agent_type}"
        )

    if input_payload is None:
        input_payload = {}

    if not isinstance(input_payload, dict):
        raise TypeError(
            "Agent input payload must be a dictionary."
        )

    workflow = (
        WorkflowRun.objects
        .select_for_update()
        .get(pk=workflow_id)
    )

    if workflow.status != WorkflowRun.Status.RUNNING:
        raise WorkflowNotRunning(
            "Agents can only be assigned to running workflows."
        )

    # Ensure that only one agent is active per workflow.
    active_execution = AgentExecution.objects.filter(
        workflow_run=workflow,
        status__in=(
            AgentExecution.Status.QUEUED,
            AgentExecution.Status.RUNNING,
        ),
    ).first()

    if active_execution:
        raise ActiveAgentExecutionExists(
            f"Workflow already has active execution "
            f"{active_execution.id}."
        )

    # Determine the next attempt number.
    previous_attempt = AgentExecution.objects.filter(
        workflow_run=workflow,
        agent_type=agent_type,
    ).aggregate(
        maximum=Max("attempt")
    )["maximum"] or 0

    next_attempt = previous_attempt + 1

    execution = AgentExecution.objects.create(
        workflow_run=workflow,
        agent_type=agent_type,
        attempt=next_attempt,
        input_payload=input_payload,
    )

    # Update the current workflow stage.
    new_stage = AGENT_STAGE_MAPPING[agent_type]

    if workflow.current_stage != new_stage:
        previous_stage = workflow.current_stage

        workflow.current_stage = new_stage

        workflow.save(
            update_fields=[
                "current_stage",
                "updated_at",
            ]
        )

        _record_agent_event(
            execution,
            "workflow.stage_changed",
            payload={
                "previous_stage": previous_stage,
                "new_stage": new_stage,
            },
            source=WorkflowEvent.Source.SYSTEM,
        )

    _record_agent_event(
        execution,
        "agent.queued",
        payload={
            "input_keys": list(input_payload.keys()),
        },
        source=WorkflowEvent.Source.SYSTEM,
    )

    return execution


@transaction.atomic
def start_agent_execution(
    execution_id,
    celery_task_id=None,
):
    """
    Starts a queued agent execution.

    Returns:
        (execution, claimed)

    claimed=True means this caller successfully
    acquired the execution and may perform the work.

    claimed=False means another worker already started it.
    """

    execution_reference = (
        AgentExecution.objects
        .only("workflow_run_id")
        .get(pk=execution_id)
    )

    workflow = (
        WorkflowRun.objects
        .select_for_update()
        .get(pk=execution_reference.workflow_run_id)
    )

    execution = (
        AgentExecution.objects
        .select_for_update()
        .get(pk=execution_id)
    )

    if workflow.status != WorkflowRun.Status.RUNNING:
        raise WorkflowNotRunning(
            "Cannot execute an agent for a non-running workflow."
        )

    # Protect against duplicate background task delivery.
    if execution.status == AgentExecution.Status.RUNNING:
        return execution, False

    if execution.status != AgentExecution.Status.QUEUED:
        raise InvalidAgentExecutionTransition(
            f"Cannot start execution with status "
            f"{execution.status}."
        )

    execution.status = AgentExecution.Status.RUNNING
    execution.started_at = timezone.now()

    if celery_task_id:
        execution.celery_task_id = celery_task_id

    execution.save(
        update_fields=[
            "status",
            "started_at",
            "celery_task_id",
            "updated_at",
        ]
    )

    _record_agent_event(
        execution,
        "agent.started",
        payload={
            "celery_task_id": celery_task_id,
        },
    )

    return execution, True


@transaction.atomic
def complete_agent_execution(
    execution_id,
    output_payload=None,
):
    """
    Marks an agent execution as successful
    and persists its structured output.
    """

    if output_payload is None:
        output_payload = {}

    if not isinstance(output_payload, dict):
        raise TypeError(
            "Agent output payload must be a dictionary."
        )

    execution_reference = (
        AgentExecution.objects
        .only("workflow_run_id")
        .get(pk=execution_id)
    )

    WorkflowRun.objects.select_for_update().get(
        pk=execution_reference.workflow_run_id
    )

    execution = (
        AgentExecution.objects
        .select_for_update()
        .get(pk=execution_id)
    )

    # Idempotency: don't duplicate completion events.
    if execution.status == AgentExecution.Status.SUCCEEDED:
        return execution

    if execution.status != AgentExecution.Status.RUNNING:
        raise InvalidAgentExecutionTransition(
            f"Cannot complete execution with status "
            f"{execution.status}."
        )

    execution.status = AgentExecution.Status.SUCCEEDED
    execution.output_payload = output_payload
    execution.finished_at = timezone.now()

    execution.save(
        update_fields=[
            "status",
            "output_payload",
            "finished_at",
            "updated_at",
        ]
    )

    _record_agent_event(
        execution,
        "agent.completed",
        payload={
            "output_keys": list(output_payload.keys()),
        },
    )

    return execution


@transaction.atomic
def fail_agent_execution(
    execution_id,
    error_code,
    error_message,
):
    """
    Records an agent execution failure.

    Failure does not automatically fail the entire workflow.
    The workflow orchestrator decides whether to retry,
    skip or terminate the workflow.
    """

    execution_reference = (
        AgentExecution.objects
        .only("workflow_run_id")
        .get(pk=execution_id)
    )

    WorkflowRun.objects.select_for_update().get(
        pk=execution_reference.workflow_run_id
    )

    execution = (
        AgentExecution.objects
        .select_for_update()
        .get(pk=execution_id)
    )

    if execution.status == AgentExecution.Status.FAILED:
        return execution

    if execution.status not in {
        AgentExecution.Status.QUEUED,
        AgentExecution.Status.RUNNING,
    }:
        raise InvalidAgentExecutionTransition(
            f"Cannot fail execution with status "
            f"{execution.status}."
        )

    execution.status = AgentExecution.Status.FAILED
    execution.error_code = error_code[:80]
    execution.error_message = error_message[:4000]
    execution.finished_at = timezone.now()

    execution.save(
        update_fields=[
            "status",
            "error_code",
            "error_message",
            "finished_at",
            "updated_at",
        ]
    )

    _record_agent_event(
        execution,
        "agent.failed",
        payload={
            "error_code": execution.error_code,
        },
    )

    return execution


@transaction.atomic
def skip_agent_execution(execution_id):
    """
    Marks a queued execution as skipped.
    """

    execution_reference = (
        AgentExecution.objects
        .only("workflow_run_id")
        .get(pk=execution_id)
    )

    WorkflowRun.objects.select_for_update().get(
        pk=execution_reference.workflow_run_id
    )

    execution = (
        AgentExecution.objects
        .select_for_update()
        .get(pk=execution_id)
    )

    if execution.status == AgentExecution.Status.SKIPPED:
        return execution

    if execution.status != AgentExecution.Status.QUEUED:
        raise InvalidAgentExecutionTransition(
            f"Cannot skip execution with status "
            f"{execution.status}."
        )

    execution.status = AgentExecution.Status.SKIPPED
    execution.finished_at = timezone.now()

    execution.save(
        update_fields=[
            "status",
            "finished_at",
            "updated_at",
        ]
    )

    _record_agent_event(
        execution,
        "agent.skipped",
        source=WorkflowEvent.Source.SYSTEM,
    )

    return execution