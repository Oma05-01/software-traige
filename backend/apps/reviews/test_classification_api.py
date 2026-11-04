from django.contrib.auth import get_user_model
from django.urls import reverse

from rest_framework import status
from rest_framework.test import APITestCase
from unittest.mock import patch
from apps.agents.models import AgentExecution
from apps.agents.services import (
    complete_agent_execution,
    create_agent_execution,
    start_agent_execution,
)
from apps.reviews.models import ClassificationReview
from apps.reviews.services import create_classification_review
from apps.tickets.models import Ticket
from apps.workflow.models import WorkflowRun
from apps.workflow.services import (
    advance_workflow_stage,
    create_workflow_for_ticket,
    transition_workflow,
)


User = get_user_model()


class ClassificationReviewAPITests(APITestCase):

    def setUp(self):
        self.ticket = Ticket.objects.create(
            title="Application crashes when saving reports",
            description="The application crashes when saving large reports.",
            reporter_email="reporter@example.com",
            environment="Windows 11, Chrome",
        )

        self.workflow = create_workflow_for_ticket(
            self.ticket.id,
        )

        transition_workflow(
            self.workflow.id,
            WorkflowRun.Status.RUNNING,
        )

        execution = create_agent_execution(
            self.workflow.id,
            AgentExecution.AgentType.RECEPTIONIST,
            {"ticket_id": str(self.ticket.id)},
        )

        execution, _ = start_agent_execution(execution.id)

        self.execution = complete_agent_execution(
            execution.id,
            {
                "category": Ticket.Category.BUG,
                "priority": Ticket.Priority.HIGH,
                "classification_confidence": "medium",
                "needs_human_review": True,
            },
        )

        self.review = create_classification_review(
            self.execution.id,
        )

        transition_workflow(
            self.workflow.id,
            WorkflowRun.Status.AWAITING_REVIEW,
        )

        advance_workflow_stage(
            self.workflow.id,
            WorkflowRun.Stage.HUMAN_REVIEW,
        )

        self.staff_user = User.objects.create_user(
            username="classification-reviewer",
            password="test-password",
            is_staff=True,
        )

        self.regular_user = User.objects.create_user(
            username="regular-user",
            password="test-password",
            is_staff=False,
        )

        self.list_url = reverse(
            "reviews:classification-list",
        )

        self.detail_url = reverse(
            "reviews:classification-detail",
            kwargs={"pk": self.review.id},
        )

        self.resolve_url = reverse(
            "reviews:classification-resolve",
            kwargs={"pk": self.review.id},
        )

    def authenticate_staff(self):
        self.client.force_authenticate(
            user=self.staff_user,
        )

    def test_anonymous_user_cannot_list_classifications(self):
        response = self.client.get(self.list_url)

        self.assertIn(
            response.status_code,
            [
                status.HTTP_401_UNAUTHORIZED,
                status.HTTP_403_FORBIDDEN,
            ],
        )

    def test_regular_user_cannot_list_classifications(self):
        self.client.force_authenticate(
            user=self.regular_user,
        )

        response = self.client.get(self.list_url)

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_staff_can_list_pending_classifications(self):
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

    def test_staff_can_list_all_classifications(self):
        self.authenticate_staff()

        response = self.client.get(
            self.list_url,
            {"status": "all"},
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(len(response.data), 1)

    def test_staff_can_retrieve_classification_detail(self):
        self.authenticate_staff()

        response = self.client.get(self.detail_url)

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            response.data["proposed_category"],
            Ticket.Category.BUG,
        )

        self.assertEqual(
            response.data["proposed_priority"],
            Ticket.Priority.HIGH,
        )

        self.assertEqual(
            response.data["ticket_title"],
            self.ticket.title,
        )

        self.assertEqual(
            response.data["status"],
            ClassificationReview.Status.PENDING,
        )

    def test_staff_can_resolve_classification(self):
        self.authenticate_staff()

        with patch(
            "apps.agents.tasks.dispatch_debugger_workflow"
        ) as dispatch:
            with self.captureOnCommitCallbacks(execute=True):
                response = self.client.post(
                    self.resolve_url,
                    {
                        "resolved_category": "bug",
                        "resolved_priority": "high",
                        "decision_note": "Confirmed by staff.",
                    },
                    format="json",
                )

            dispatch.assert_called_once_with(
                str(self.workflow.id)
            )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            response.data["status"],
            ClassificationReview.Status.RESOLVED,
        )

        self.assertEqual(
            response.data["decision"],
            ClassificationReview.Decision.CONFIRMED,
        )

    def test_regular_user_cannot_resolve_classification(self):
        self.client.force_authenticate(
            user=self.regular_user,
        )

        response = self.client.post(
            self.resolve_url,
            {
                "resolved_category": "bug",
                "resolved_priority": "high",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_other_category_is_rejected_by_resolution_api(self):
        self.authenticate_staff()

        response = self.client.post(
            self.resolve_url,
            {
                "resolved_category": "other",
                "resolved_priority": "medium",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        self.review.refresh_from_db()

        self.assertEqual(
            self.review.status,
            ClassificationReview.Status.PENDING,
        )

    def test_unassessed_priority_is_rejected(self):
        self.authenticate_staff()

        response = self.client.post(
            self.resolve_url,
            {
                "resolved_category": "bug",
                "resolved_priority": "unassessed",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_resolved_classification_cannot_be_resolved_again(self):
        self.authenticate_staff()

        payload = {
            "resolved_category": "bug",
            "resolved_priority": "high",
        }

        first = self.client.post(
            self.resolve_url,
            payload,
            format="json",
        )

        second = self.client.post(
            self.resolve_url,
            payload,
            format="json",
        )

        self.assertEqual(
            first.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            second.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_invalid_status_filter_is_rejected(self):
        self.authenticate_staff()

        response = self.client.get(
            self.list_url,
            {"status": "unknown"},
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_staff_can_filter_classifications_by_workflow(self):
        self.authenticate_staff()

        response = self.client.get(
            self.list_url,
            {
                "status": "all",
                "workflow_run_id": str(self.workflow.id),
            },
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(len(response.data), 1)

        self.assertEqual(
            str(response.data[0]["workflow_run_id"]),
            str(self.workflow.id),
        )


    def test_invalid_workflow_filter_is_rejected(self):
        self.authenticate_staff()

        response = self.client.get(
            self.list_url,
            {
                "workflow_run_id": "not-a-uuid",
            },
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )