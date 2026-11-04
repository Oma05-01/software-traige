
import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q
from apps.agents.models import AgentExecution
from apps.tickets.models import Ticket
from apps.workflow.models import WorkflowRun


class ReviewRequest(models.Model):
    """
    A human-reviewable proposal for one specific external action.

    Approval of one action does not authorize another action.
    """

    class ActionType(models.TextChoices):
        SEND_SUPPORT_RESPONSE = (
            "send_support_response",
            "Send support response",
        )
        CREATE_GITHUB_ISSUE = (
            "create_github_issue",
            "Create GitHub issue",
        )

    class Status(models.TextChoices):
        PENDING = "pending", "Pending review"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        CHANGES_REQUESTED = "changes_requested", "Changes requested"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    workflow_run = models.ForeignKey(
        "workflow.WorkflowRun",
        on_delete=models.PROTECT,
        related_name="review_requests",
    )

    revision_number = models.PositiveIntegerField(default=1)

    agent_execution = models.ForeignKey(
        "agents.AgentExecution",
        on_delete=models.PROTECT,
        related_name="review_requests",
    )

    action_type = models.CharField(
        max_length=50,
        choices=ActionType.choices,
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )

    # Snapshot of exactly what is being proposed for approval.
    proposed_payload = models.JSONField(default=dict)

    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="review_decisions",
    )

    reviewed_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    decision_note = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

        constraints = [
            models.UniqueConstraint(
                fields=["agent_execution", "action_type"],
                name="uniq_agent_action_review",
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        status="pending",
                        reviewed_by__isnull=True,
                        reviewed_at__isnull=True,
                    )
                    |
                    Q(
                        status__in=[
                            "changes_requested",
                            "approved",
                            "rejected",
                        ],
                        reviewed_by__isnull=False,
                        reviewed_at__isnull=False,
                    )
                ),
                name="review_decision_fields_ok",
            ),
        ]

        indexes = [
            models.Index(
                fields=["status", "created_at"],
                name="review_status_created_idx",
            ),
            models.Index(
                fields=["workflow_run", "status"],
                name="review_workflow_status_idx",
            ),
        ]

    def __str__(self):
        return (
            f"{self.action_type} - {self.status} "
            f"({self.workflow_run_id})"
        )

class ClassificationReview(models.Model):

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        RESOLVED = "resolved", "Resolved"

    class Decision(models.TextChoices):
        CONFIRMED = "confirmed", "Confirmed"
        CORRECTED = "corrected", "Corrected"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    # One classification decision per workflow.
    workflow_run = models.OneToOneField(
        WorkflowRun,
        on_delete=models.PROTECT,
        related_name="classification_review",
    )

    # The Receptionist execution that produced the suggestion.
    agent_execution = models.OneToOneField(
        AgentExecution,
        on_delete=models.PROTECT,
        related_name="classification_review",
    )

    # Original agent suggestion. These values are never overwritten.
    proposed_category = models.CharField(
        max_length=20,
        choices=Ticket.Category.choices,
    )

    proposed_priority = models.CharField(
        max_length=20,
        choices=Ticket.Priority.choices,
    )

    classification_confidence = models.CharField(
        max_length=20,
        blank=True,
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )

    # Staff resolution.
    decision = models.CharField(
        max_length=20,
        choices=Decision.choices,
        blank=True,
        default="",
    )

    resolved_category = models.CharField(
        max_length=20,
        choices=Ticket.Category.choices,
        blank=True,
        default="",
    )

    resolved_priority = models.CharField(
        max_length=20,
        choices=Ticket.Priority.choices,
        blank=True,
        default="",
    )

    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="resolved_classification_reviews",
    )

    reviewed_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    decision_note = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

        indexes = [
            models.Index(
                fields=["status", "created_at"],
                name="clrev_stat_created_idx",
            ),
        ]

        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(
                        status="pending",
                        decision="",
                        resolved_category="",
                        resolved_priority="",
                        reviewed_by__isnull=True,
                        reviewed_at__isnull=True,
                    )
                    |
                    models.Q(
                        status="resolved",
                        decision__in=["confirmed", "corrected"],
                        resolved_category__in=[
                            Ticket.Category.BUG,
                            Ticket.Category.FEATURE,
                            Ticket.Category.OTHER,
                            Ticket.Category.SPAM,
                        ],
                        resolved_priority__in=[
                            Ticket.Priority.LOW,
                            Ticket.Priority.MEDIUM,
                            Ticket.Priority.HIGH,
                            Ticket.Priority.CRITICAL,
                        ],
                        reviewed_by__isnull=False,
                        reviewed_at__isnull=False,
                    )
                ),
                name="classification_review_state_valid",
            ),
        ]

    def __str__(self):
        return (
            f"Classification review - "
            f"{self.workflow_run_id} ({self.status})"
        )