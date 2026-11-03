from django.contrib.auth import get_user_model
from django.urls import reverse

from rest_framework import status
from rest_framework.test import APITestCase

from apps.agents.models import AgentExecution
from apps.agents.services import (
    complete_agent_execution,
    create_agent_execution,
    start_agent_execution,
)
from apps.reviews.models import ReviewRequest
from apps.reviews.services import create_review_request
from apps.tickets.models import Ticket
from apps.workflow.models import WorkflowRun
from apps.workflow.services import (
    advance_workflow_stage,
    create_workflow_for_ticket,
    transition_workflow,
)


User = get_user_model()


class ReviewRequestAPITests(APITestCase):

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
            {"ticket_id": str(self.ticket.id)},
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

        self.review = create_review_request(
            self.execution.id,
        )

        self.staff_user = User.objects.create_user(
            username="reviewer",
            password="test-password",
            is_staff=True,
        )

        self.regular_user = User.objects.create_user(
            username="regular",
            password="test-password",
            is_staff=False,
        )

        self.list_url = reverse("reviews:review-list")

        self.detail_url = reverse(
            "reviews:review-detail",
            kwargs={"pk": self.review.id},
        )

    @staticmethod
    def support_response_payload():
        return {
            "draft_status": "pending_human_review",
            "subject": "Update on your report",
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

    def authenticate_staff(self):
        self.client.force_authenticate(user=self.staff_user)

    def test_anonymous_user_cannot_list_reviews(self):
        response = self.client.get(self.list_url)

        self.assertIn(
            response.status_code,
            [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN],
        )

    def test_regular_user_cannot_list_reviews(self):
        self.client.force_authenticate(
            user=self.regular_user,
        )

        response = self.client.get(self.list_url)

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_staff_can_list_pending_reviews(self):
        self.authenticate_staff()

        response = self.client.get(self.list_url)

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(len(response.data), 1)
        self.assertEqual(
            str(response.data[0]["id"]),
            str(self.review.id),
        )

    def test_staff_can_retrieve_review_detail(self):
        self.authenticate_staff()

        response = self.client.get(self.detail_url)

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            response.data["action_type"],
            ReviewRequest.ActionType.SEND_SUPPORT_RESPONSE,
        )

    def test_staff_can_edit_pending_proposal(self):
        self.authenticate_staff()

        updated_payload = self.review.proposed_payload.copy()
        updated_payload["draft_response"] = (
            "This is the revised response."
        )

        response = self.client.patch(
            reverse(
                "reviews:review-edit",
                kwargs={"pk": self.review.id},
            ),
            {"proposed_payload": updated_payload},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            response.data["proposed_payload"]["draft_response"],
            "This is the revised response.",
        )

    def test_staff_can_approve_review(self):
        self.authenticate_staff()

        response = self.client.post(
            reverse(
                "reviews:review-approve",
                kwargs={"pk": self.review.id},
            ),
            {"decision_note": "Approved after review."},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            response.data["status"],
            ReviewRequest.Status.APPROVED,
        )

        self.workflow.refresh_from_db()

        self.assertEqual(
            self.workflow.status,
            WorkflowRun.Status.AWAITING_REVIEW,
        )

    def test_staff_can_reject_review(self):
        self.authenticate_staff()

        response = self.client.post(
            reverse(
                "reviews:review-reject",
                kwargs={"pk": self.review.id},
            ),
            {"decision_note": "Please revise the response."},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            response.data["status"],
            ReviewRequest.Status.REJECTED,
        )

    def test_cannot_approve_the_same_review_twice(self):
        self.authenticate_staff()

        url = reverse(
            "reviews:review-approve",
            kwargs={"pk": self.review.id},
        )

        first = self.client.post(url, {}, format="json")
        second = self.client.post(url, {}, format="json")

        self.assertEqual(
            first.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            second.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_invalid_proposal_cannot_be_approved(self):
        self.authenticate_staff()

        payload = self.review.proposed_payload.copy()
        payload["external_send_authorized"] = True

        response = self.client.patch(
            reverse(
                "reviews:review-edit",
                kwargs={"pk": self.review.id},
            ),
            {"proposed_payload": payload},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_staff_can_request_changes(self):
        self.authenticate_staff()

        url = reverse(
            "reviews:review-request-changes",
            kwargs={"pk": self.review.id},
        )

        response = self.client.post(
            url,
            {
                "decision_note": (
                    "Please clarify the technical explanation."
                )
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            response.data["status"],
            ReviewRequest.Status.CHANGES_REQUESTED,
        )


def test_staff_can_resubmit_revised_proposal(self):
    self.authenticate_staff()

    changes_url = reverse(
        "reviews:review-request-changes",
        kwargs={"pk": self.review.id},
    )

    changes_response = self.client.post(
        changes_url,
        {
            "decision_note": "Please improve the response."
        },
        format="json",
    )

    self.assertEqual(
        changes_response.status_code,
        status.HTTP_200_OK,
    )

    revised_payload = self.review.proposed_payload.copy()

    revised_payload["draft_response"] = (
        "Thank you for reporting this issue. "
        "We have updated our response and would "
        "like to clarify one additional detail."
    )

    revise_url = reverse(
        "reviews:review-revise",
        kwargs={"pk": self.review.id},
    )

    response = self.client.patch(
        revise_url,
        {"proposed_payload": revised_payload},
        format="json",
    )

    self.assertEqual(
        response.status_code,
        status.HTTP_200_OK,
    )

    self.assertEqual(
        response.data["status"],
        ReviewRequest.Status.PENDING,
    )

    self.assertEqual(
        response.data["revision_number"],
        2,
    )

    self.assertIsNone(
        response.data["reviewed_by"],
    )

    self.assertEqual(
        response.data["decision_note"],
        "",
    )