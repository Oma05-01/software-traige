from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.agents.models import AgentExecution
from apps.agents.services import (
    complete_agent_execution,
    create_agent_execution,
    start_agent_execution,
)
from apps.events.models import WorkflowEvent
from apps.reviews.models import ClassificationReview
from apps.reviews.services import (
    InvalidReviewAction,
    create_classification_review,
    resolve_classification_review,
)
from apps.tickets.models import Ticket
from apps.workflow.models import WorkflowRun
from apps.workflow.services import (
    advance_workflow_stage,
    create_workflow_for_ticket,
    transition_workflow,
)

User = get_user_model()


class ClassificationReviewResolutionTests(TestCase):

    def setUp(self):
        self.ticket = Ticket.objects.create(
            title="Application crashes when saving reports",
            description="The application crashes when saving large reports.",
            reporter_email="reporter@example.com",
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

        advance_workflow_stage(
            self.workflow.id,
            WorkflowRun.Stage.HUMAN_REVIEW,
        )

        transition_workflow(
            self.workflow.id,
            WorkflowRun.Status.AWAITING_REVIEW,
        )

        self.reviewer = User.objects.create_user(
            username="classification-reviewer",
            password="test-password",
            is_staff=True,
        )

        self.regular_user = User.objects.create_user(
            username="regular-user",
            password="test-password",
            is_staff=False,
        )

    def resolve(self, category, priority, reviewer=None):
        return resolve_classification_review(
            self.review.id,
            reviewer or self.reviewer,
            category,
            priority,
            "Classification reviewed.",
        )

    def test_staff_can_confirm_proposed_classification(self):
        with patch(
            "apps.agents.tasks.dispatch_debugger_workflow"
        ) as dispatch:
            with self.captureOnCommitCallbacks(
                execute=True
            ) as callbacks:

                resolved = self.resolve(
                    Ticket.Category.BUG,
                    Ticket.Priority.HIGH,
                )

                dispatch.assert_not_called()

            self.assertEqual(len(callbacks), 1)
            dispatch.assert_called_once_with(
                str(self.workflow.id)
            )

        self.assertEqual(
            resolved.status,
            ClassificationReview.Status.RESOLVED,
        )

        self.assertEqual(
            resolved.decision,
            ClassificationReview.Decision.CONFIRMED,
        )

        self.ticket.refresh_from_db()
        self.workflow.refresh_from_db()

        self.assertEqual(
            self.ticket.category,
            Ticket.Category.BUG,
        )

        self.assertEqual(
            self.ticket.priority,
            Ticket.Priority.HIGH,
        )

        self.assertEqual(
            self.ticket.status,
            Ticket.Status.IN_PROGRESS,
        )

        self.assertEqual(
            self.workflow.status,
            WorkflowRun.Status.RUNNING,
        )

        self.assertEqual(
            self.workflow.current_stage,
            WorkflowRun.Stage.DEBUGGER,
        )

    def test_staff_can_correct_classification(self):
        with patch(
            "apps.agents.tasks.dispatch_product_manager_workflow"
        ) as dispatch:
            with self.captureOnCommitCallbacks(execute=True):
                resolved = self.resolve(
                    Ticket.Category.FEATURE,
                    Ticket.Priority.MEDIUM,
                )

            dispatch.assert_called_once_with(
                str(self.workflow.id)
            )

        self.assertEqual(
            resolved.decision,
            ClassificationReview.Decision.CORRECTED,
        )

        self.assertEqual(
            resolved.proposed_category,
            Ticket.Category.BUG,
        )

        self.assertEqual(
            resolved.resolved_category,
            Ticket.Category.FEATURE,
        )

        self.assertEqual(
            resolved.resolved_priority,
            Ticket.Priority.MEDIUM,
        )

        self.ticket.refresh_from_db()
        self.workflow.refresh_from_db()

        self.assertEqual(
            self.ticket.category,
            Ticket.Category.FEATURE,
        )

        self.assertEqual(
            self.workflow.current_stage,
            WorkflowRun.Stage.PRODUCT_MANAGER,
        )

    def test_non_staff_user_cannot_resolve_classification(self):
        with self.assertRaises(InvalidReviewAction):
            self.resolve(
                Ticket.Category.BUG,
                Ticket.Priority.HIGH,
                reviewer=self.regular_user,
            )

        self.review.refresh_from_db()

        self.assertEqual(
            self.review.status,
            ClassificationReview.Status.PENDING,
        )

    def test_other_and_spam_cannot_be_automatically_routed(self):
        for category in (
            Ticket.Category.OTHER,
            Ticket.Category.SPAM,
        ):
            with self.subTest(category=category):
                with self.assertRaises(InvalidReviewAction):
                    self.resolve(
                        category,
                        Ticket.Priority.MEDIUM,
                    )

        self.review.refresh_from_db()

        self.assertEqual(
            self.review.status,
            ClassificationReview.Status.PENDING,
        )

    def test_unassessed_priority_cannot_be_confirmed(self):
        with self.assertRaises(InvalidReviewAction):
            self.resolve(
                Ticket.Category.BUG,
                Ticket.Priority.UNASSESSED,
            )

        self.review.refresh_from_db()

        self.assertEqual(
            self.review.status,
            ClassificationReview.Status.PENDING,
        )

    def test_classification_cannot_be_resolved_twice(self):
        with self.captureOnCommitCallbacks(execute=False):
            self.resolve(
                Ticket.Category.BUG,
                Ticket.Priority.HIGH,
            )

            with self.assertRaises(InvalidReviewAction):
                self.resolve(
                    Ticket.Category.BUG,
                    Ticket.Priority.HIGH,
                )

        self.assertEqual(
            WorkflowEvent.objects.filter(
                workflow_run=self.workflow,
                event_type="classification.review_resolved",
            ).count(),
            1,
        )