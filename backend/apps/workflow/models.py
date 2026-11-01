import uuid

from django.db import models
from django.db.models import Q

from apps.tickets.models import Ticket


# Statuses that count as active workflows.
ACTIVE_WORKFLOW_STATUSES = (
    "queued",
    "running",
    "awaiting_review",
)


class WorkflowRun(models.Model):

    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        RUNNING = "running", "Running"
        AWAITING_REVIEW = "awaiting_review", "Awaiting Review"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    class Stage(models.TextChoices):
        RECEPTIONIST = "receptionist", "Receptionist"
        DEBUGGER = "debugger", "Debugger"
        PRODUCT_MANAGER = "product_manager", "Product Manager"
        SUPPORT_REP = "support_rep", "Support Rep"
        HUMAN_REVIEW = "human_review", "Human Review"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    ticket = models.ForeignKey(
        Ticket,
        on_delete=models.PROTECT,
        related_name="workflow_runs",
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.QUEUED,
        db_index=True,
    )

    current_stage = models.CharField(
        max_length=30,
        choices=Stage.choices,
        default=Stage.RECEPTIONIST,
    )

    workflow_version = models.CharField(
        max_length=20,
        default="1.0",
    )

    # Execution timestamps
    started_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    finished_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    # Sanitized failure information
    error_code = models.CharField(
        max_length=80,
        blank=True,
    )

    error_message = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

        indexes = [
            models.Index(
                fields=["status", "created_at"],
                name="workflow_status_created_idx",
            ),
        ]

        constraints = [
            models.UniqueConstraint(
                fields=["ticket"],
                condition=Q(
                    status__in=ACTIVE_WORKFLOW_STATUSES
                ),
                name="one_active_workflow_per_ticket",
            ),
        ]

    def __str__(self):
        return (
            f"Workflow {self.id} - "
            f"{self.ticket.title} ({self.status})"
        )