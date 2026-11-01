from celery import shared_task

from apps.agents.runner import run_receptionist
from apps.workflow.models import WorkflowRun
from apps.workflow.services import transition_workflow


@shared_task(
    bind=True,
    name="apps.agents.process_ticket_workflow",
    ignore_result=True,
)
def process_ticket_workflow(self, workflow_id):
    """
    Background entry point for ticket processing.

    Starts a queued workflow and executes its Receptionist.
    """

    workflow = WorkflowRun.objects.get(pk=workflow_id)

    if workflow.status == WorkflowRun.Status.QUEUED:

        workflow = transition_workflow(
            workflow.id,
            WorkflowRun.Status.RUNNING,
        )

    elif workflow.status != WorkflowRun.Status.RUNNING:
        # Ignore duplicate or obsolete task deliveries.
        return None

    execution = run_receptionist(
        workflow.id,
        celery_task_id=self.request.id,
    )

    return str(execution.id)