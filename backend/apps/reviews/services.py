
from copy import deepcopy

from django.db import transaction
from django.utils import timezone

from apps.agents.models import AgentExecution
from apps.events.models import WorkflowEvent
from apps.reviews.models import ReviewRequest
from apps.workflow.services import record_workflow_event


class InvalidReviewAction(Exception):
    """Raised when a review action is invalid or unauthorized."""


def require_staff_reviewer(reviewer):
    """Ensure that review decisions are made by active staff users."""

    if (
        reviewer is None
        or not getattr(reviewer, "is_authenticated", False)
        or not getattr(reviewer, "is_active", False)
        or not getattr(reviewer, "is_staff", False)
    ):
        raise InvalidReviewAction(
            "An authenticated, active staff reviewer is required."
        )


def validate_proposal(action_type, payload):
    """Validate the proposed content for the requested action."""

    if not isinstance(payload, dict):
        raise TypeError("Proposed payload must be a dictionary.")

    if action_type == ReviewRequest.ActionType.SEND_SUPPORT_RESPONSE:

        if payload.get("draft_status") != "pending_human_review":
            raise InvalidReviewAction(
                "The support response must be a pending draft."
            )

        if not isinstance(payload.get("draft_response"), str):
            raise InvalidReviewAction(
                "The support response draft must be text."
            )

        if not payload["draft_response"].strip():
            raise InvalidReviewAction(
                "The support response draft cannot be empty."
            )

        if payload.get("requires_human_review") is not True:
            raise InvalidReviewAction(
                "The support response must require human review."
            )

        if payload.get("external_send_authorized") is not False:
            raise InvalidReviewAction(
                "The draft cannot authorize external delivery."
            )


@transaction.atomic
def create_review_request(agent_execution_id):
    """
    Create one pending review request from a successful Support Rep
    execution.

    Repeated calls return the existing request rather than creating
    duplicates.
    """

    execution = AgentExecution.objects.select_for_update().get(
        pk=agent_execution_id,
    )

    if execution.agent_type != AgentExecution.AgentType.SUPPORT_REP:
        raise InvalidReviewAction(
            "Only a Support Rep execution can create this review request."
        )

    if execution.status != AgentExecution.Status.SUCCEEDED:
        raise InvalidReviewAction(
            "The Support Rep execution must have succeeded."
        )

    payload = execution.output_payload

    validate_proposal(
        ReviewRequest.ActionType.SEND_SUPPORT_RESPONSE,
        payload,
    )

    review_request, created = ReviewRequest.objects.get_or_create(
        agent_execution=execution,
        action_type=ReviewRequest.ActionType.SEND_SUPPORT_RESPONSE,
        defaults={
            "workflow_run_id": execution.workflow_run_id,
            "proposed_payload": deepcopy(payload),
            "status": ReviewRequest.Status.PENDING,
        },
    )

    if created:
        record_workflow_event(
            execution.workflow_run_id,
            event_type="review.requested",
            source=WorkflowEvent.Source.AGENT,
            payload={
                "review_request_id": str(review_request.id),
                "agent_execution_id": str(execution.id),
                "action_type": review_request.action_type,
                "status": review_request.status,
            },
        )

    return review_request


@transaction.atomic
def update_review_proposal(
    review_request_id,
    reviewer,
    proposed_payload,
):
    """Edit a pending proposal while preserving its previous version."""

    require_staff_reviewer(reviewer)

    review_request = ReviewRequest.objects.select_for_update().get(
        pk=review_request_id,
    )

    if review_request.status != ReviewRequest.Status.PENDING:
        raise InvalidReviewAction(
            "Only pending review requests can be edited."
        )

    validate_proposal(
        review_request.action_type,
        proposed_payload,
    )

    previous_payload = deepcopy(review_request.proposed_payload)

    review_request.proposed_payload = deepcopy(proposed_payload)
    review_request.revision_number += 1

    review_request.save(
        update_fields=[
            "proposed_payload",
            "revision_number",
            "updated_at",
        ],
    )

    record_workflow_event(
        review_request.workflow_run_id,
        event_type="review.proposal_edited",
        source=WorkflowEvent.Source.HUMAN,
        payload={
            "review_request_id": str(review_request.id),
            "reviewer_id": str(reviewer.pk),
            "revision_number": review_request.revision_number,
            "previous_proposed_payload": previous_payload,
            "proposed_payload": deepcopy(proposed_payload),
        },
    )

    return review_request


@transaction.atomic
def approve_review_request(
    review_request_id,
    reviewer,
    decision_note="",
):
    """
    Approve one specific proposed action.

    Approval does not execute or send the action.
    """

    require_staff_reviewer(reviewer)

    review_request = ReviewRequest.objects.select_for_update().get(
        pk=review_request_id,
    )

    if review_request.status != ReviewRequest.Status.PENDING:
        raise InvalidReviewAction(
            "Only pending review requests can be approved."
        )

    review_request.status = ReviewRequest.Status.APPROVED
    review_request.reviewed_by = reviewer
    review_request.reviewed_at = timezone.now()
    review_request.decision_note = decision_note.strip()

    review_request.save(
        update_fields=[
            "status",
            "reviewed_by",
            "reviewed_at",
            "decision_note",
            "updated_at",
        ],
    )

    record_workflow_event(
        review_request.workflow_run_id,
        event_type="review.approved",
        source=WorkflowEvent.Source.HUMAN,
        payload={
            "review_request_id": str(review_request.id),
            "reviewer_id": str(reviewer.pk),
            "action_type": review_request.action_type,
        },
    )

    return review_request


@transaction.atomic
def reject_review_request(
    review_request_id,
    reviewer,
    decision_note="",
):
    """Reject one specific proposed action."""

    require_staff_reviewer(reviewer)

    review_request = ReviewRequest.objects.select_for_update().get(
        pk=review_request_id,
    )

    if review_request.status != ReviewRequest.Status.PENDING:
        raise InvalidReviewAction(
            "Only pending review requests can be rejected."
        )

    review_request.status = ReviewRequest.Status.REJECTED
    review_request.reviewed_by = reviewer
    review_request.reviewed_at = timezone.now()
    review_request.decision_note = decision_note.strip()

    review_request.save(
        update_fields=[
            "status",
            "reviewed_by",
            "reviewed_at",
            "decision_note",
            "updated_at",
        ],
    )

    record_workflow_event(
        review_request.workflow_run_id,
        event_type="review.rejected",
        source=WorkflowEvent.Source.HUMAN,
        payload={
            "review_request_id": str(review_request.id),
            "reviewer_id": str(reviewer.pk),
            "action_type": review_request.action_type,
        },
    )

    return review_request

@transaction.atomic
def request_review_changes(
    review_request_id,
    reviewer,
    decision_note,
):
    """
    Return a pending proposal for revision.

    This is not the same as rejecting the proposed action.
    """

    require_staff_reviewer(reviewer)

    if not isinstance(decision_note, str) or not decision_note.strip():
        raise InvalidReviewAction(
            "A decision note is required when requesting changes."
        )

    review_request = ReviewRequest.objects.select_for_update().get(
        pk=review_request_id,
    )

    if review_request.status != ReviewRequest.Status.PENDING:
        raise InvalidReviewAction(
            "Only pending review requests can have changes requested."
        )

    review_request.status = ReviewRequest.Status.CHANGES_REQUESTED
    review_request.reviewed_by = reviewer
    review_request.reviewed_at = timezone.now()
    review_request.decision_note = decision_note.strip()

    review_request.save(
        update_fields=[
            "status",
            "reviewed_by",
            "reviewed_at",
            "decision_note",
            "updated_at",
        ],
    )

    record_workflow_event(
        review_request.workflow_run_id,
        event_type="review.changes_requested",
        source=WorkflowEvent.Source.HUMAN,
        payload={
            "review_request_id": str(review_request.id),
            "reviewer_id": str(reviewer.pk),
            "action_type": review_request.action_type,
            "decision_note": review_request.decision_note,
            "revision_number": review_request.revision_number,
        },
    )

    return review_request

@transaction.atomic
def revise_review_request(
    review_request_id,
    reviewer,
    proposed_payload,
):
    """
    Submit a revised proposal after a reviewer requests changes.

    The previous proposal and decision are preserved in the workflow
    event history. The review request returns to pending status.
    """

    require_staff_reviewer(reviewer)

    review_request = ReviewRequest.objects.select_for_update().get(
        pk=review_request_id,
    )

    if review_request.status != ReviewRequest.Status.CHANGES_REQUESTED:
        raise InvalidReviewAction(
            "Only review requests with changes requested can be revised."
        )

    validate_proposal(
        review_request.action_type,
        proposed_payload,
    )

    previous_payload = deepcopy(review_request.proposed_payload)

    previous_decision = {
        "reviewer_id": (
            str(review_request.reviewed_by_id)
            if review_request.reviewed_by_id
            else None
        ),
        "reviewed_at": (
            review_request.reviewed_at.isoformat()
            if review_request.reviewed_at
            else None
        ),
        "decision_note": review_request.decision_note,
    }

    review_request.proposed_payload = deepcopy(proposed_payload)
    review_request.revision_number += 1

    # Start a fresh review decision cycle.
    review_request.status = ReviewRequest.Status.PENDING
    review_request.reviewed_by = None
    review_request.reviewed_at = None
    review_request.decision_note = ""

    review_request.save(
        update_fields=[
            "proposed_payload",
            "revision_number",
            "status",
            "reviewed_by",
            "reviewed_at",
            "decision_note",
            "updated_at",
        ],
    )

    record_workflow_event(
        review_request.workflow_run_id,
        event_type="review.revision_submitted",
        source=WorkflowEvent.Source.HUMAN,
        payload={
            "review_request_id": str(review_request.id),
            "reviewer_id": str(reviewer.pk),
            "revision_number": review_request.revision_number,
            "previous_decision": previous_decision,
            "previous_proposed_payload": previous_payload,
            "proposed_payload": deepcopy(proposed_payload),
        },
    )

    return review_request

