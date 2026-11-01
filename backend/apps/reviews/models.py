
import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q


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
                        status__in=["approved", "rejected"],
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
