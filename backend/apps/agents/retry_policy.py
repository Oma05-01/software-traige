
import logging

from django.db import transaction

from apps.events.models import WorkflowEvent
from apps.tickets.models import Ticket
from apps.workflow.models import WorkflowRun
from apps.workflow.services import transition_workflow


logger = logging.getLogger(__name__)


MAX_AGENT_RETRIES = 2

AGENT_RETRY_DELAYS = (30, 60)

AGENT_STAGES = {
    "receptionist": WorkflowRun.Stage.RECEPTIONIST,
    "debugger": WorkflowRun.Stage.DEBUGGER,
    "product_manager": WorkflowRun.Stage.PRODUCT_MANAGER,
    "support_rep": WorkflowRun.Stage.SUPPORT_REP,
}


def _lock_workflow_for_retry(workflow_id, expected_stage):
    """
    Lock the ticket and workflow in the same order used
    by the workflow transition service.
    """

    ticket_id = WorkflowRun.objects.values_list(
        "ticket_id",
        flat=True,
    ).get(pk=workflow_id)

    Ticket.objects.select_for_update().get(pk=ticket_id)

    workflow = (
        WorkflowRun.objects
        .select_for_update()
        .get(pk=workflow_id)
    )

    if workflow.status != WorkflowRun.Status.RUNNING:
        return None

    if workflow.current_stage != expected_stage:
        return None

    return workflow


def _record_retry_scheduled(
    workflow_id,
    agent_type,
    retry_number,
    countdown,
    error_type,
    celery_task_id,
):
    """
    Record a retry request only if the workflow is still
    running at the expected agent stage.
    """

    expected_stage = AGENT_STAGES[agent_type]

    with transaction.atomic():
        workflow = _lock_workflow_for_retry(
            workflow_id,
            expected_stage,
        )

        if workflow is None:
            return False

        WorkflowEvent.objects.create(
            workflow_run=workflow,
            event_type="workflow.agent_retry_scheduled",
            source=WorkflowEvent.Source.SYSTEM,
            payload={
                "agent_type": agent_type,
                "retry_number": retry_number,
                "max_retries": MAX_AGENT_RETRIES,
                "countdown_seconds": countdown,
                "error_type": error_type,
                "celery_task_id": celery_task_id,
            },
        )

    return True


def _fail_workflow_after_retry_exhaustion(
    workflow_id,
    agent_type,
    retries_used,
    error_type,
    celery_task_id,
):
    """
    Atomically record retry exhaustion and fail the
    workflow, provided it is still at the failed agent stage.
    """

    expected_stage = AGENT_STAGES[agent_type]

    with transaction.atomic():
        workflow = _lock_workflow_for_retry(
            workflow_id,
            expected_stage,
        )

        if workflow is None:
            return False

        workflow.error_code = "AGENT_RETRY_EXHAUSTED"
        workflow.error_message = (
            f"The {agent_type} agent exhausted its "
            f"transient provider retry budget "
            f"after {retries_used} retries."
        )

        workflow.save(
            update_fields=[
                "error_code",
                "error_message",
                "updated_at",
            ],
        )

        WorkflowEvent.objects.create(
            workflow_run=workflow,
            event_type="workflow.agent_retry_exhausted",
            source=WorkflowEvent.Source.SYSTEM,
            payload={
                "agent_type": agent_type,
                "retries_used": retries_used,
                "total_attempts": retries_used + 1,
                "max_retries": MAX_AGENT_RETRIES,
                "error_type": error_type,
                "celery_task_id": celery_task_id,
            },
        )

        transition_workflow(
            workflow.id,
            WorkflowRun.Status.FAILED,
            source=WorkflowEvent.Source.SYSTEM,
        )

    return True


def handle_transient_agent_failure(
    task,
    workflow_id,
    agent_type,
    exc,
):
    """
    Apply the shared bounded Celery retry policy.

    Initial execution:
        request.retries == 0

    First retry:
        request.retries == 1

    Second retry:
        request.retries == 2

    After the second retry fails, terminate the workflow.
    """

    if agent_type not in AGENT_STAGES:
        raise ValueError(
            f"Unsupported agent type: {agent_type}"
        )

    retries_used = int(
        getattr(task.request, "retries", 0) or 0
    )

    celery_task_id = getattr(
        task.request,
        "id",
        None,
    )

    error_type = type(exc).__name__

    if retries_used < MAX_AGENT_RETRIES:
        retry_number = retries_used + 1
        countdown = AGENT_RETRY_DELAYS[retries_used]

        recorded = _record_retry_scheduled(
            workflow_id=workflow_id,
            agent_type=agent_type,
            retry_number=retry_number,
            countdown=countdown,
            error_type=error_type,
            celery_task_id=celery_task_id,
        )

        if not recorded:
            logger.info(
                "Skipping retry for %s on workflow %s "
                "because its workflow stage has changed.",
                agent_type,
                workflow_id,
            )
            return False

        logger.warning(
            "Scheduling retry %s/%s for %s on workflow %s "
            "in %s seconds.",
            retry_number,
            MAX_AGENT_RETRIES,
            agent_type,
            workflow_id,
            countdown,
        )

        raise task.retry(
            exc=exc,
            countdown=countdown,
            max_retries=MAX_AGENT_RETRIES,
        )

    failed = _fail_workflow_after_retry_exhaustion(
        workflow_id=workflow_id,
        agent_type=agent_type,
        retries_used=retries_used,
        error_type=error_type,
        celery_task_id=celery_task_id,
    )

    if not failed:
        logger.info(
            "Skipping retry exhaustion handling for %s "
            "on workflow %s because its workflow stage "
            "has changed.",
            agent_type,
            workflow_id,
        )
        return False

    logger.error(
        "Retry budget exhausted for %s on workflow %s. "
        "The workflow has been marked as failed.",
        agent_type,
        workflow_id,
    )

    raise exc
