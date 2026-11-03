from celery import shared_task

from apps.integrations.services import execute_action_execution


@shared_task(
    bind=True,
    name="apps.integrations.execute_action_execution",
    ignore_result=True,
)
def execute_action_execution_task(self, execution_id):
    """
    Execute one approved action.

    The execution service performs the authorization checks
    and duplicate-delivery protection.
    """

    execution = execute_action_execution(execution_id)

    return str(execution.id)