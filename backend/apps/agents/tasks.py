
import logging

from celery import shared_task

from apps.agents.models import AgentExecution
from apps.agents.runner import run_receptionist
from apps.agents.debugger_runner import run_debugger
from apps.agents.support_rep_runner import run_support_rep
from apps.events.models import WorkflowEvent
from apps.tickets.models import Ticket
from apps.workflow.models import WorkflowRun
from apps.workflow.services import transition_workflow
from apps.agents.product_manager_runner import run_product_manager
from apps.agents.llm.base import LLMTransientError
from apps.agents.retry_policy import (
    handle_transient_agent_failure,
)

logger = logging.getLogger(__name__)

def _is_redelivered(task):
    """Return whether the broker redelivered this task message."""

    delivery_info = (
        getattr(task.request, "delivery_info", None) or {}
    )

    return bool(delivery_info.get("redelivered", False))


def record_dispatch_failure(workflow_id, agent_type, exc):
    """Record a dispatch failure and fail the affected workflow."""

    logger.exception(
        "Could not dispatch %s task for workflow %s",
        agent_type,
        workflow_id,
    )

    WorkflowEvent.objects.create(
        workflow_run_id=workflow_id,
        event_type="workflow.dispatch_failed",
        source=WorkflowEvent.Source.SYSTEM,
        payload={
            "agent_type": agent_type,
            "error_type": type(exc).__name__,
        },
    )

    workflow = WorkflowRun.objects.get(pk=workflow_id)

    if workflow.status == WorkflowRun.Status.RUNNING:
        transition_workflow(
            workflow_id,
            WorkflowRun.Status.FAILED,
            source=WorkflowEvent.Source.SYSTEM,
        )

def dispatch_debugger_workflow(workflow_id):
    """Queue the Debugger after successful Receptionist execution."""

    try:
        process_debugger_workflow.delay(str(workflow_id))

        logger.info(
            "Dispatched Debugger task for workflow %s",
            workflow_id,
        )

    except Exception as exc:
        record_dispatch_failure(
            workflow_id,
            "debugger",
            exc,
        )

def dispatch_product_manager_workflow(workflow_id):
    """Queue the Product Manager after feature classification."""

    try:
        process_product_manager_workflow.delay(str(workflow_id))

        logger.info(
            "Dispatched Product Manager task for workflow %s",
            workflow_id,
        )

    except Exception as exc:
        record_dispatch_failure(
            workflow_id,
            "product_manager",
            exc,
        )

def dispatch_support_rep_workflow(workflow_id):
    """Queue the Support Rep after successful Debugger execution."""

    try:
        process_support_rep_workflow.delay(str(workflow_id))

        logger.info(
            "Dispatched Support Rep task for workflow %s",
            workflow_id,
        )

    except Exception as exc:
        record_dispatch_failure(
            workflow_id,
            "support_rep",
            exc,
        )


@shared_task(
    bind=True,
    name="apps.agents.process_ticket_workflow",
    ignore_result=True,
)
def process_ticket_workflow(self, workflow_id):
    """
    Start a queued workflow and execute the Receptionist.

    Bug tickets proceed to the Debugger.
    """

    workflow = WorkflowRun.objects.get(pk=workflow_id)

    if workflow.status == WorkflowRun.Status.QUEUED:
        workflow = transition_workflow(
            workflow.id,
            WorkflowRun.Status.RUNNING,
        )

    elif workflow.status != WorkflowRun.Status.RUNNING:
        return None

    try:
        execution = run_receptionist(
            workflow.id,
            celery_task_id=self.request.id,
            redelivered=_is_redelivered(self),
        )

    except LLMTransientError as exc:
        handle_transient_agent_failure(
            task=self,
            workflow_id=workflow.id,
            agent_type="receptionist",
            exc=exc,
        )
        return None

    workflow.refresh_from_db(
        fields=["status", "current_stage"],
    )

    ticket_category = Ticket.objects.values_list(
        "category",
        flat=True,
    ).get(pk=workflow.ticket_id)

    should_run_debugger = (
        execution.status == AgentExecution.Status.SUCCEEDED
        and workflow.status == WorkflowRun.Status.RUNNING
        and workflow.current_stage == WorkflowRun.Stage.DEBUGGER
        and ticket_category == Ticket.Category.BUG
    )

    if should_run_debugger:
        dispatch_debugger_workflow(workflow.id)

    should_run_product_manager = (
        execution.status == AgentExecution.Status.SUCCEEDED
        and workflow.status == WorkflowRun.Status.RUNNING
        and workflow.current_stage == WorkflowRun.Stage.PRODUCT_MANAGER
        and ticket_category == Ticket.Category.FEATURE
    )

    if should_run_product_manager:
        dispatch_product_manager_workflow(workflow.id)

    return str(execution.id)


@shared_task(
    bind=True,
    name="apps.agents.process_debugger_workflow",
    ignore_result=True,
)
def process_debugger_workflow(self, workflow_id):
    """
    Execute the Debugger and dispatch the Support Rep
    after successful investigation.
    """

    workflow = WorkflowRun.objects.select_related("ticket").get(
        pk=workflow_id,
    )

    if workflow.status != WorkflowRun.Status.RUNNING:
        return None

    if workflow.current_stage != WorkflowRun.Stage.DEBUGGER:
        return None

    if workflow.ticket.category != Ticket.Category.BUG:
        return None

    try:
        execution = run_debugger(
        workflow.id,
        celery_task_id=self.request.id,
        redelivered=_is_redelivered(self),
    )

    except LLMTransientError as exc:
        handle_transient_agent_failure(
            task=self,
            workflow_id=workflow.id,
            agent_type="debugger",
            exc=exc,
        )
        return None

    workflow.refresh_from_db(
        fields=["status", "current_stage"],
    )

    should_run_support_rep = (
        execution.status == AgentExecution.Status.SUCCEEDED
        and workflow.status == WorkflowRun.Status.RUNNING
        and workflow.current_stage == WorkflowRun.Stage.SUPPORT_REP
    )

    if should_run_support_rep:
        dispatch_support_rep_workflow(workflow.id)

    return str(execution.id)


@shared_task(
    bind=True,
    name="apps.agents.process_support_rep_workflow",
    ignore_result=True,
)
def process_support_rep_workflow(self, workflow_id):
    """
    Execute the Support Rep for a workflow at its Support Rep stage.

    The Support Rep prepares a draft and transitions the workflow
    to human review. It does not send external messages.
    """

    workflow = WorkflowRun.objects.select_related("ticket").get(
        pk=workflow_id,
    )

    if workflow.status != WorkflowRun.Status.RUNNING:
        return None

    if workflow.current_stage != WorkflowRun.Stage.SUPPORT_REP:
        return None

    try:
        execution = run_support_rep(
            workflow.id,
            celery_task_id=self.request.id,
            redelivered=_is_redelivered(self),
        )

    except LLMTransientError as exc:
        handle_transient_agent_failure(
            task=self,
            workflow_id=workflow.id,
            agent_type="support_rep",
            exc=exc,
        )
        return None

    return str(execution.id)

@shared_task(
    bind=True,
    name="apps.agents.process_product_manager_workflow",
    ignore_result=True,
)
def process_product_manager_workflow(self, workflow_id):
    """
    Execute Product Manager and dispatch Support Rep
    after a successful feature assessment.
    """

    workflow = WorkflowRun.objects.select_related("ticket").get(
        pk=workflow_id,
    )

    if workflow.status != WorkflowRun.Status.RUNNING:
        return None

    if workflow.current_stage != WorkflowRun.Stage.PRODUCT_MANAGER:
        return None

    if workflow.ticket.category != Ticket.Category.FEATURE:
        return None

    try:
        execution = run_product_manager(
            workflow.id,
            celery_task_id=self.request.id,
            redelivered=_is_redelivered(self),
        )

    except LLMTransientError as exc:
        handle_transient_agent_failure(
            task=self,
            workflow_id=workflow.id,
            agent_type="product_manager",
            exc=exc,
        )
        return None

    workflow.refresh_from_db(
        fields=["status", "current_stage"],
    )

    should_run_support_rep = (
        execution.status == AgentExecution.Status.SUCCEEDED
        and workflow.status == WorkflowRun.Status.RUNNING
        and workflow.current_stage == WorkflowRun.Stage.SUPPORT_REP
    )

    if should_run_support_rep:
        dispatch_support_rep_workflow(workflow.id)

    return str(execution.id)
