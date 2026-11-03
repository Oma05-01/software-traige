import logging

from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.events.models import WorkflowEvent
from apps.integrations.models import ActionExecution
from apps.integrations.providers.mock_email import MockEmailProvider
from apps.reviews.models import ReviewRequest
from apps.workflow.services import record_workflow_event
from apps.workflow.models import WorkflowRun
from apps.workflow.services import transition_workflow


logger = logging.getLogger(__name__)


class ActionNotAuthorized(Exception):
    """Raised when an action has not been properly authorized."""


class ActionExecutionNotReady(Exception):
    """Raised when an action cannot currently be executed."""


def record_action_event(execution, event_type, payload):
    record_workflow_event(
        execution.review_request.workflow_run_id,
        event_type=event_type,
        source=WorkflowEvent.Source.INTEGRATION,
        payload={
            "action_execution_id": str(execution.id),
            "review_request_id": str(execution.review_request_id),
            "action_type": execution.action_type,
            "provider": execution.provider,
            **payload,
        },
    )


@transaction.atomic
def create_action_execution(review_request_id):
    """
    Create an ActionExecution from an approved ReviewRequest.

    The approved proposal is copied into a new immutable request
    snapshot. Repeated calls return the existing execution.
    """

    review = (
    ReviewRequest.objects
    .select_for_update(of=("self",))
    .select_related(
        "workflow_run__ticket",
        "reviewed_by",
    )
    .get(pk=review_request_id)
)

    if review.status != ReviewRequest.Status.APPROVED:
        raise ActionNotAuthorized(
            "Only approved review requests can be executed."
        )

    if review.reviewed_by_id is None or review.reviewed_at is None:
        raise ActionNotAuthorized(
            "The review request has no valid approval record."
        )

    if (
        review.action_type
        != ReviewRequest.ActionType.SEND_SUPPORT_RESPONSE
    ):
        raise ActionNotAuthorized(
            "This action type is not supported yet."
        )

    proposal = review.proposed_payload

    if not isinstance(proposal, dict):
        raise ActionNotAuthorized(
            "The approved proposal is invalid."
        )

    if proposal.get("draft_status") != "pending_human_review":
        raise ActionNotAuthorized(
            "The approved support response is not a valid draft."
        )

    if proposal.get("requires_human_review") is not True:
        raise ActionNotAuthorized(
            "The support response does not contain a valid review requirement."
        )

    if proposal.get("external_send_authorized") is not False:
        raise ActionNotAuthorized(
            "The proposal contains an invalid authorization flag."
        )

    ticket = review.workflow_run.ticket
    recipient = (ticket.reporter_email or "").strip()

    if not recipient:
        raise ActionNotAuthorized(
            "The ticket has no reporter email address."
        )

    try:
        validate_email(recipient)
    except ValidationError as exc:
        raise ActionNotAuthorized(
            "The ticket reporter email address is invalid."
        ) from exc

    subject = proposal.get("subject")
    body = proposal.get("draft_response")

    if not isinstance(subject, str) or not subject.strip():
        raise ActionNotAuthorized("The approved subject is empty.")

    if not isinstance(body, str) or not body.strip():
        raise ActionNotAuthorized("The approved response is empty.")

    idempotency_key = (
        f"review:{review.id}:action:{review.action_type}"
    )

    request_payload = {
        "recipient": recipient,
        "subject": subject,
        "body": body,
    }

    execution, created = ActionExecution.objects.get_or_create(
        review_request=review,
        defaults={
            "action_type": review.action_type,
            "provider": ActionExecution.Provider.MOCK_EMAIL,
            "status": ActionExecution.Status.QUEUED,
            "idempotency_key": idempotency_key,
            "request_payload": request_payload,
        },
    )

    if execution.action_type != review.action_type:
        raise ActionNotAuthorized(
            "The execution action type does not match its review request."
        )

    # An existing execution must retain the exact approved snapshot.
    if execution.request_payload != request_payload:
        raise ActionNotAuthorized(
            "The existing execution snapshot differs from the approved proposal."
        )

    if created:
        record_action_event(
            execution,
            "action.execution_queued",
            {
                "status": execution.status,
                "attempt_count": execution.attempt_count,
            },
        )

    return execution


def dispatch_action_execution(execution_id):
    """
    Dispatch the execution task after the database transaction commits.

    If the broker is unavailable, leave the record queued and
    record a dispatch failure for later recovery.
    """

    try:
        from apps.integrations.tasks import execute_action_execution_task

        execute_action_execution_task.delay(str(execution_id))

    except Exception as exc:
        logger.exception(
            "Failed to dispatch action execution %s",
            execution_id,
        )

        execution = ActionExecution.objects.select_related(
            "review_request"
        ).get(pk=execution_id)

        record_action_event(
            execution,
            "action.dispatch_failed",
            {
                "error_type": type(exc).__name__,
            },
        )


@transaction.atomic
def queue_action_execution(review_request_id):
    """
    Create or retrieve an approved action execution and queue it.

    Duplicate requests reuse the same ActionExecution.
    """

    execution = create_action_execution(review_request_id)

    if execution.status == ActionExecution.Status.FAILED:
        raise ActionExecutionNotReady(
            "This action previously failed. Explicit recovery is required."
        )

    if execution.status in (
        ActionExecution.Status.SUCCEEDED,
        ActionExecution.Status.RUNNING,
    ):
        return execution

    execution_id = str(execution.id)

    transaction.on_commit(
        lambda: dispatch_action_execution(execution_id)
    )

    return execution


@transaction.atomic
def claim_action_execution(execution_id):
    """
    Atomically claim a queued action.

    Duplicate Celery deliveries cannot claim an execution
    that is already running or completed.
    """

    execution = ActionExecution.objects.select_for_update().select_related(
        "review_request",
    ).get(pk=execution_id)

    if execution.status in (
        ActionExecution.Status.RUNNING,
        ActionExecution.Status.SUCCEEDED,
    ):
        return execution, False

    if execution.status == ActionExecution.Status.FAILED:
        raise ActionExecutionNotReady(
            "Failed actions require explicit recovery."
        )

    if execution.status != ActionExecution.Status.QUEUED:
        raise ActionExecutionNotReady(
            "The action execution is not queued."
        )

    review = ReviewRequest.objects.select_for_update().get(
        pk=execution.review_request_id,
    )

    if review.status != ReviewRequest.Status.APPROVED:
        raise ActionNotAuthorized(
            "The associated review request is not approved."
        )

    if review.action_type != execution.action_type:
        raise ActionNotAuthorized(
            "The action type no longer matches its review request."
        )

    execution.status = ActionExecution.Status.RUNNING
    execution.attempt_count += 1
    execution.started_at = timezone.now()
    execution.error_code = ""
    execution.error_message = ""

    execution.save(
        update_fields=[
            "status",
            "attempt_count",
            "started_at",
            "error_code",
            "error_message",
            "updated_at",
        ],
    )

    record_action_event(
        execution,
        "action.execution_started",
        {
            "attempt_count": execution.attempt_count,
        },
    )

    return execution, True


def execute_action_execution(execution_id, provider=None):
    """
    Execute a claimed approved action through the selected provider.

    A successful mock execution does not mean an actual email was sent.
    Workflow state is updated according to the actual delivery outcome.
    """

    provider = provider or MockEmailProvider()

    execution, should_execute = claim_action_execution(
        execution_id
    )

    if not should_execute:
        return execution

    workflow_id = ReviewRequest.objects.values_list(
        "workflow_run_id",
        flat=True,
    ).get(pk=execution.review_request_id)

    try:
        # The action has been claimed. Mark the workflow as processing.
        # This is idempotent when the workflow is already RUNNING.
        transition_workflow(
            workflow_id,
            WorkflowRun.Status.RUNNING,
        )

        if execution.provider != ActionExecution.Provider.MOCK_EMAIL:
            raise ActionExecutionNotReady(
                "The configured provider is not supported."
            )

        if execution.action_type != (
            ActionExecution.ActionType.SEND_SUPPORT_RESPONSE
        ):
            raise ActionExecutionNotReady(
                "The configured action type is not supported."
            )

        result = provider.send(
            recipient=execution.request_payload["recipient"],
            subject=execution.request_payload["subject"],
            body=execution.request_payload["body"],
            idempotency_key=execution.idempotency_key,
        )

        if not isinstance(result, dict):
            raise TypeError(
                "Provider result must be a dictionary."
            )

        if result.get("accepted") is not True:
            raise RuntimeError(
                "Provider did not accept the action."
            )

        external_delivery_performed = result.get(
            "external_delivery_performed",
            False,
        )

        if not isinstance(external_delivery_performed, bool):
            raise TypeError(
                "external_delivery_performed must be a boolean."
            )

        # The mock provider must never claim actual external delivery.
        if (
            execution.provider == ActionExecution.Provider.MOCK_EMAIL
            and external_delivery_performed
        ):
            raise ValueError(
                "Mock provider cannot report external delivery."
            )

    except Exception as exc:

        with transaction.atomic():
            transition_workflow(
                workflow_id,
                WorkflowRun.Status.AWAITING_REVIEW,
            )

            current = ActionExecution.objects.select_for_update().get(
                pk=execution.id,
            )

            current.status = ActionExecution.Status.FAILED
            current.finished_at = timezone.now()
            current.error_code = type(exc).__name__
            current.error_message = str(exc)[:2000]

            current.save(
                update_fields=[
                    "status",
                    "finished_at",
                    "error_code",
                    "error_message",
                    "updated_at",
                ],
            )

            record_action_event(
                current,
                "action.execution_failed",
                {
                    "error_type": type(exc).__name__,
                    "attempt_count": current.attempt_count,
                },
            )

        raise

    # An accepted mock action is not the same as an externally
    # delivered response.
    next_workflow_status = WorkflowRun.Status.COMPLETED

    with transaction.atomic():

        # Complete the workflow through the permitted lifecycle.
        # RUNNING -> AWAITING_REVIEW -> COMPLETED.
        transition_workflow(
            workflow_id,
            WorkflowRun.Status.AWAITING_REVIEW,
        )

        transition_workflow(
            workflow_id,
            next_workflow_status,
        )

        completed = ActionExecution.objects.select_for_update().get(
            pk=execution.id,
        )

        completed.status = ActionExecution.Status.SUCCEEDED
        completed.provider_response = result
        completed.finished_at = timezone.now()
        completed.error_code = ""
        completed.error_message = ""

        completed.save(
            update_fields=[
                "status",
                "provider_response",
                "finished_at",
                "error_code",
                "error_message",
                "updated_at",
            ],
        )

        record_action_event(
            completed,
            "action.execution_succeeded",
            {
                "attempt_count": completed.attempt_count,
                "delivery_mode": result.get("delivery_mode"),
                "external_delivery_performed": (
                    external_delivery_performed
                ),
            },
        )

    return completed