from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from apps.workflow.models import WorkflowRun
from apps.events.models import WorkflowEvent
from apps.tickets.models import Ticket
from .models import AgentExecution

import uuid

from apps.tickets.models import Ticket

class ActiveAgentExecutionExists(Exception):
    """Raised when a workflow already has an active agent execution."""


class WorkflowNotRunning(Exception):
    """Raised when an agent is assigned to an inactive workflow."""

class InvalidAgentExecutionTransition(Exception):
    """Raised when an agent execution transition is invalid."""

class StaleAgentExecutionClaim(InvalidAgentExecutionTransition):
    """Raised when a worker attempts to use an obsolete claim token."""


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

MAX_WORKER_LOSS_RECOVERIES = 2


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


def _fail_execution_after_worker_loss(
    workflow,
    execution,
):
    """
    Fail the execution and workflow when the worker-loss
    recovery budget has been exhausted.

    The caller must already hold locks on the ticket,
    workflow and execution, in that order.
    """

    now = timezone.now()

    execution.status = AgentExecution.Status.FAILED
    execution.error_code = "WORKER_LOSS_RECOVERY_EXHAUSTED"
    execution.error_message = (
        "The worker repeatedly terminated before "
        "the agent execution could complete."
    )
    execution.finished_at = now

    execution.save(
        update_fields=[
            "status",
            "error_code",
            "error_message",
            "finished_at",
            "updated_at",
        ]
    )

    WorkflowEvent.objects.create(
        workflow_run=workflow,
        event_type="agent.worker_loss_recovery_exhausted",
        source=WorkflowEvent.Source.SYSTEM,
        payload={
            "agent_type": execution.agent_type,
            "worker_loss_recoveries": (
                execution.worker_loss_recoveries
            ),
            "max_recoveries": MAX_WORKER_LOSS_RECOVERIES,
            "celery_task_id": execution.celery_task_id,
        },
    )

    workflow.error_code = "AGENT_WORKER_LOSS_EXHAUSTED"
    workflow.error_message = (
        f"The {execution.agent_type} agent exhausted "
        "its worker-loss recovery budget."
    )

    workflow.save(
        update_fields=[
            "error_code",
            "error_message",
            "updated_at",
        ]
    )

    WorkflowEvent.objects.create(
        workflow_run=workflow,
        event_type="workflow.agent_worker_loss_recovery_exhausted",
        source=WorkflowEvent.Source.SYSTEM,
        payload={
            "agent_type": execution.agent_type,
            "execution_id": str(execution.id),
            "worker_loss_recoveries": (
                execution.worker_loss_recoveries
            ),
            "celery_task_id": execution.celery_task_id,
        },
    )

    from apps.workflow.services import transition_workflow

    transition_workflow(
        workflow.id,
        WorkflowRun.Status.FAILED,
        source=WorkflowEvent.Source.SYSTEM,
    )


@transaction.atomic
def start_agent_execution(
    execution_id,
    celery_task_id=None,
    redelivered=False,
):
    """
    Starts or safely recovers an agent execution.

    Returns:
        (execution, claimed)

    A normal duplicate delivery cannot claim an execution
    that is already running.

    A broker-redelivered task can reclaim an execution
    only when its Celery task ID matches the original claim.

    Each successful claim receives a fresh fencing token.
    """

    execution_reference = (
        AgentExecution.objects
        .only("workflow_run_id")
        .get(pk=execution_id)
    )

    ticket_id = WorkflowRun.objects.values_list(
        "ticket_id",
        flat=True,
    ).get(pk=execution_reference.workflow_run_id)

    # Maintain the global lock order:
    # Ticket -> WorkflowRun -> AgentExecution.
    Ticket.objects.select_for_update().get(
        pk=ticket_id,
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

    # An already-running execution is recoverable only
    # through a genuine broker redelivery with the same
    # Celery task ID.
    if execution.status == AgentExecution.Status.RUNNING:

        if (
            not redelivered
            or not celery_task_id
            or execution.celery_task_id != celery_task_id
        ):
            return execution, False

        # The recovery budget is exhausted.
        if (
            execution.worker_loss_recoveries
            >= MAX_WORKER_LOSS_RECOVERIES
        ):
            _fail_execution_after_worker_loss(
                workflow,
                execution,
            )

            return execution, False

        # Reclaim the SAME execution with a new fencing token.
        execution.worker_loss_recoveries += 1
        execution.claim_token = uuid.uuid4()

        execution.save(
            update_fields=[
                "worker_loss_recoveries",
                "claim_token",
                "updated_at",
            ]
        )

        WorkflowEvent.objects.create(
            workflow_run=workflow,
            event_type="agent.worker_loss_recovered",
            source=WorkflowEvent.Source.SYSTEM,
            payload={
                "agent_type": execution.agent_type,
                "execution_id": str(execution.id),
                "recovery_number": (
                    execution.worker_loss_recoveries
                ),
                "max_recoveries": MAX_WORKER_LOSS_RECOVERIES,
                "celery_task_id": celery_task_id,
            },
        )

        return execution, True

    if execution.status != AgentExecution.Status.QUEUED:
        raise InvalidAgentExecutionTransition(
            f"Cannot start execution with status "
            f"{execution.status}."
        )

    # Initial claim, including a redelivery that occurred
    # before the execution had been claimed.
    execution.status = AgentExecution.Status.RUNNING
    execution.started_at = timezone.now()
    execution.claim_token = uuid.uuid4()

    if celery_task_id:
        execution.celery_task_id = celery_task_id

    execution.save(
        update_fields=[
            "status",
            "started_at",
            "celery_task_id",
            "claim_token",
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
    claim_token=None,
):
    """
    Marks an agent execution as successful and persists
    its structured output.

    When claim_token is supplied, only the worker holding
    the current claim may complete the execution.
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

    ticket_id = WorkflowRun.objects.values_list(
        "ticket_id",
        flat=True,
    ).get(pk=execution_reference.workflow_run_id)

    # Consistent lock order:
    # Ticket -> WorkflowRun -> AgentExecution.
    Ticket.objects.select_for_update().get(
        pk=ticket_id,
    )

    WorkflowRun.objects.select_for_update().get(
        pk=execution_reference.workflow_run_id,
    )

    execution = (
        AgentExecution.objects
        .select_for_update()
        .get(pk=execution_id)
    )

    # Validate ownership before the idempotency check.
    # An obsolete worker must not receive permission to
    # continue persistence merely because the execution
    # has already completed.
    if (
        claim_token is not None
        and execution.claim_token != claim_token
    ):
        raise StaleAgentExecutionClaim(
            "This worker no longer owns the agent execution."
        )

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
    claim_token=None,
):
    """
    Records an agent execution failure.

    When claim_token is supplied, only the current worker
    holding that claim may fail the execution.

    Failure does not automatically fail the workflow.
    """

    execution_reference = (
        AgentExecution.objects
        .only("workflow_run_id")
        .get(pk=execution_id)
    )

    ticket_id = WorkflowRun.objects.values_list(
        "ticket_id",
        flat=True,
    ).get(pk=execution_reference.workflow_run_id)

    # Consistent lock order:
    # Ticket -> WorkflowRun -> AgentExecution.
    Ticket.objects.select_for_update().get(
        pk=ticket_id,
    )

    WorkflowRun.objects.select_for_update().get(
        pk=execution_reference.workflow_run_id,
    )

    execution = (
        AgentExecution.objects
        .select_for_update()
        .get(pk=execution_id)
    )

    if (
        claim_token is not None
        and execution.claim_token != claim_token
    ):
        raise StaleAgentExecutionClaim(
            "This worker no longer owns the agent execution."
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


def record_transient_agent_failure(
    execution_id,
    claim_token=None,
):
    """
    Record a temporary provider failure without terminating
    the workflow.

    The current claim token prevents an obsolete worker
    from recording failure against a recovered execution.
    """

    return fail_agent_execution(
        execution_id,
        error_code="LLM_TRANSIENT_FAILURE",
        error_message=(
            "A temporary LLM provider failure occurred. "
            "The Celery task retry policy determines recovery."
        ),
        claim_token=claim_token,
    )

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