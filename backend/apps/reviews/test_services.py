from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.agents.models import AgentExecution
from apps.agents.services import (
    complete_agent_execution,
    create_agent_execution,
    start_agent_execution,
)
from apps.events.models import WorkflowEvent
from apps.reviews.models import ReviewRequest
from apps.reviews.services import (
    InvalidReviewAction,
    approve_review_request,
    create_review_request,
    reject_review_request,
    update_review_proposal,
    revise_review_request,
    request_review_changes,
)
from apps.tickets.models import Ticket
from apps.workflow.models import WorkflowRun
from apps.workflow.services import (
    advance_workflow_stage,
    create_workflow_for_ticket,
    transition_workflow,
)


User = get_user_model()


class ReviewRequestServiceTests(TestCase):

    def setUp(self):
        self.ticket = Ticket.objects.create(
            title="PDF upload failure",
            description=(
                "The application crashes when uploading "
                "PDF files larger than 25 MB."
            ),
            reporter_name="Test Reporter",
            reporter_email="reporter@example.com",
            environment="Windows 11, Chrome",
            category=Ticket.Category.BUG,
            priority=Ticket.Priority.HIGH,
        )

        self.workflow = create_workflow_for_ticket(
            self.ticket.id,
        )

        transition_workflow(
            self.workflow.id,
            WorkflowRun.Status.RUNNING,
        )

        advance_workflow_stage(
            self.workflow.id,
            WorkflowRun.Stage.DEBUGGER,
        )

        advance_workflow_stage(
            self.workflow.id,
            WorkflowRun.Stage.SUPPORT_REP,
        )

        self.execution = create_agent_execution(
            self.workflow.id,
            AgentExecution.AgentType.SUPPORT_REP,
            {
                "ticket_id": str(self.ticket.id),
            },
        )

        self.execution, _ = start_agent_execution(
            self.execution.id,
        )

        complete_agent_execution(
            self.execution.id,
            self.support_response_payload(),
        )

        advance_workflow_stage(
            self.workflow.id,
            WorkflowRun.Stage.HUMAN_REVIEW,
        )

        transition_workflow(
            self.workflow.id,
            WorkflowRun.Status.AWAITING_REVIEW,
        )

        self.reviewer = User.objects.create_user(
            username="reviewer",
            password="test-password",
            is_staff=True,
        )

        self.regular_user = User.objects.create_user(
            username="regular-user",
            password="test-password",
            is_staff=False,
        )

    @staticmethod
    def support_response_payload():
        return {
            "draft_status": "pending_human_review",
            "subject": "Update on your PDF upload report",
            "draft_response": (
                "Thank you for reporting this issue. "
                "We need additional information to investigate."
            ),
            "response_type": "acknowledgement",
            "follow_up_questions": [],
            "evidence_references": [],
            "internal_review_notes": [],
            "requires_human_review": True,
            "external_send_authorized": False,
            "responder": {
                "name": "deterministic_support_rep",
                "version": "1.0.0",
            },
        }

    def create_request(self):
        return create_review_request(self.execution.id)

    def test_creates_pending_support_response_review(self):
        review = self.create_request()

        self.assertEqual(
            review.action_type,
            ReviewRequest.ActionType.SEND_SUPPORT_RESPONSE,
        )

        self.assertEqual(
            review.status,
            ReviewRequest.Status.PENDING,
        )

        self.assertEqual(
            review.agent_execution,
            self.execution,
        )

        self.assertEqual(
            review.proposed_payload["draft_status"],
            "pending_human_review",
        )

        self.assertIsNone(review.reviewed_by)
        self.assertIsNone(review.reviewed_at)

    def test_review_creation_is_idempotent(self):
        first = self.create_request()
        second = self.create_request()

        self.assertEqual(first.id, second.id)

        self.assertEqual(
            ReviewRequest.objects.filter(
                agent_execution=self.execution,
                action_type=(
                    ReviewRequest.ActionType.SEND_SUPPORT_RESPONSE
                ),
            ).count(),
            1,
        )

        self.assertEqual(
            WorkflowEvent.objects.filter(
                workflow_run=self.workflow,
                event_type="review.requested",
            ).count(),
            1,
        )

    def test_only_successful_support_rep_execution_can_create_review(self):
        self.execution.agent_type = (
            AgentExecution.AgentType.DEBUGGER
        )

        self.execution.save(update_fields=["agent_type"])

        with self.assertRaises(InvalidReviewAction):
            self.create_request()

    def test_failed_execution_cannot_create_review(self):
        self.execution.status = AgentExecution.Status.FAILED
        self.execution.save(update_fields=["status"])

        with self.assertRaises(InvalidReviewAction):
            self.create_request()

    def test_invalid_support_response_cannot_be_reviewed(self):
        payload = self.execution.output_payload
        payload["external_send_authorized"] = True

        self.execution.output_payload = payload
        self.execution.save(update_fields=["output_payload"])

        with self.assertRaises(InvalidReviewAction):
            self.create_request()

    def test_staff_can_approve_a_pending_request(self):
        review = self.create_request()

        approved = approve_review_request(
            review.id,
            self.reviewer,
            "Reviewed and approved.",
        )

        self.assertEqual(
            approved.status,
            ReviewRequest.Status.APPROVED,
        )

        self.assertEqual(
            approved.reviewed_by,
            self.reviewer,
        )

        self.assertIsNotNone(approved.reviewed_at)

        self.assertEqual(
            approved.decision_note,
            "Reviewed and approved.",
        )

    def test_staff_can_reject_a_pending_request(self):
        review = self.create_request()

        rejected = reject_review_request(
            review.id,
            self.reviewer,
            "The response needs revision.",
        )

        self.assertEqual(
            rejected.status,
            ReviewRequest.Status.REJECTED,
        )

        self.assertEqual(
            rejected.reviewed_by,
            self.reviewer,
        )

    def test_non_staff_user_cannot_approve(self):
        review = self.create_request()

        with self.assertRaises(InvalidReviewAction):
            approve_review_request(
                review.id,
                self.regular_user,
            )

    def test_non_staff_user_cannot_reject(self):
        review = self.create_request()

        with self.assertRaises(InvalidReviewAction):
            reject_review_request(
                review.id,
                self.regular_user,
            )

    def test_pending_proposal_can_be_edited_by_staff(self):
        review = self.create_request()

        updated_payload = review.proposed_payload.copy()

        updated_payload["draft_response"] = (
            "Revised response prepared for review."
        )

        updated = update_review_proposal(
            review.id,
            self.reviewer,
            updated_payload,
        )

        self.assertEqual(
            updated.proposed_payload["draft_response"],
            "Revised response prepared for review.",
        )

        self.assertEqual(
            updated.status,
            ReviewRequest.Status.PENDING,
        )

    def test_approved_proposal_cannot_be_edited(self):
        review = self.create_request()

        approve_review_request(
            review.id,
            self.reviewer,
        )

        updated_payload = review.proposed_payload.copy()

        updated_payload["draft_response"] = (
            "Attempted change after approval."
        )

        with self.assertRaises(InvalidReviewAction):
            update_review_proposal(
                review.id,
                self.reviewer,
                updated_payload,
            )

    def test_review_cannot_be_approved_twice(self):
        review = self.create_request()

        approve_review_request(
            review.id,
            self.reviewer,
        )

        with self.assertRaises(InvalidReviewAction):
            approve_review_request(
                review.id,
                self.reviewer,
            )

    def test_review_cannot_be_rejected_after_approval(self):
        review = self.create_request()

        approve_review_request(
            review.id,
            self.reviewer,
        )

        with self.assertRaises(InvalidReviewAction):
            reject_review_request(
                review.id,
                self.reviewer,
            )

    def test_approval_does_not_execute_or_complete_workflow(self):
        review = self.create_request()

        approve_review_request(
            review.id,
            self.reviewer,
        )

        self.workflow.refresh_from_db()

        self.assertEqual(
            self.workflow.status,
            WorkflowRun.Status.AWAITING_REVIEW,
        )

        self.assertEqual(
            self.workflow.current_stage,
            WorkflowRun.Stage.HUMAN_REVIEW,
        )

    def test_staff_can_request_changes(self):
        review = self.create_request()

        updated = request_review_changes(
            review.id,
            self.reviewer,
            "Please clarify the technical explanation.",
        )

        self.assertEqual(
            updated.status,
            ReviewRequest.Status.CHANGES_REQUESTED,
        )

        self.assertEqual(
            updated.reviewed_by,
            self.reviewer,
        )

        self.assertEqual(
            updated.decision_note,
            "Please clarify the technical explanation.",
        )

        self.assertIsNotNone(updated.reviewed_at)


    def test_changes_requested_review_can_be_resubmitted(self):
        review = self.create_request()

        request_review_changes(
            review.id,
            self.reviewer,
            "Please clarify the response.",
        )

        revised_payload = review.proposed_payload.copy()

        revised_payload["draft_response"] = (
            "Thank you for reporting this issue. "
            "We have received your report and need one "
            "additional detail to investigate."
        )

        updated = revise_review_request(
            review.id,
            self.reviewer,
            revised_payload,
        )

        self.assertEqual(
            updated.status,
            ReviewRequest.Status.PENDING,
        )

        self.assertEqual(updated.revision_number, 2)

        self.assertIsNone(updated.reviewed_by)
        self.assertIsNone(updated.reviewed_at)
        self.assertEqual(updated.decision_note, "")

        self.assertEqual(
            updated.proposed_payload["draft_response"],
            revised_payload["draft_response"],
        )


    def test_revision_history_preserves_previous_proposal(self):
        review = self.create_request()

        original_payload = review.proposed_payload.copy()

        request_review_changes(
            review.id,
            self.reviewer,
            "Please revise the wording.",
        )

        revised_payload = original_payload.copy()
        revised_payload["draft_response"] = (
            "This is the revised support response."
        )

        revise_review_request(
            review.id,
            self.reviewer,
            revised_payload,
        )

        event = WorkflowEvent.objects.get(
            workflow_run=self.workflow,
            event_type="review.revision_submitted",
        )

        self.assertEqual(
            event.payload["previous_proposed_payload"],
            original_payload,
        )

        self.assertEqual(
            event.payload["proposed_payload"],
            revised_payload,
        )

        self.assertEqual(
            event.payload["previous_decision"]["decision_note"],
            "Please revise the wording.",
        )

        self.assertEqual(
            event.payload["revision_number"],
            2,
        )


    def test_rejected_review_cannot_be_resubmitted(self):
        review = self.create_request()

        reject_review_request(
            review.id,
            self.reviewer,
            "The proposed action is not appropriate.",
        )

        with self.assertRaises(InvalidReviewAction):
            revise_review_request(
                review.id,
                self.reviewer,
                self.support_response_payload(),
            )


    def test_changes_request_requires_a_note(self):
        review = self.create_request()

        with self.assertRaises(InvalidReviewAction):
            request_review_changes(
                review.id,
                self.reviewer,
                "   ",
            )
            