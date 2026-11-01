import uuid

from django.db import models
from django.db.models import Q

from apps.workflow.models import WorkflowRun


# Executions considered active by the database.
ACTIVE_EXECUTION_STATUSES = (
    "queued",
    "running",
)


class AgentExecution(models.Model):

    class AgentType(models.TextChoices):
        RECEPTIONIST = "receptionist", "Receptionist"
        DEBUGGER = "debugger", "Debugger"
        PRODUCT_MANAGER = "product_manager", "Product Manager"
        SUPPORT_REP = "support_rep", "Support Rep"

    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        RUNNING = "running", "Running"
        SUCCEEDED = "succeeded", "Succeeded"
        FAILED = "failed", "Failed"
        SKIPPED = "skipped", "Skipped"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    workflow_run = models.ForeignKey(
        WorkflowRun,
        on_delete=models.PROTECT,
        related_name="agent_executions",
    )

    agent_type = models.CharField(
        max_length=30,
        choices=AgentType.choices,
        db_index=True,
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.QUEUED,
        db_index=True,
    )

    # Retry tracking
    attempt = models.PositiveSmallIntegerField(
        default=1,
    )

    # Structured agent input and output
    input_payload = models.JSONField(
        default=dict,
        blank=True,
    )

    output_payload = models.JSONField(
        default=dict,
        blank=True,
    )

    # Future Celery integration
    celery_task_id = models.CharField(
        max_length=255,
        blank=True,
        db_index=True,
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

    # Sanitized error information
    error_code = models.CharField(
        max_length=80,
        blank=True,
    )

    error_message = models.TextField(
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = ["created_at", "attempt"]

        indexes = [
            models.Index(
                fields=["workflow_run", "status"],
                name="agent_workflow_status_idx",
            ),
            models.Index(
                fields=["agent_type", "created_at"],
                name="agent_type_created_idx",
            ),
        ]

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "workflow_run",
                    "agent_type",
                    "attempt",
                ],
                name="unique_agent_workflow_attempt",
            ),

            models.UniqueConstraint(
                fields=["workflow_run"],
                condition=Q(
                    status__in=ACTIVE_EXECUTION_STATUSES
                ),
                name="one_active_agent_per_workflow",
            ),

            models.CheckConstraint(
                condition=Q(attempt__gte=1),
                name="agent_attempt_at_least_one",
            ),
        ]

    def __str__(self):
        return (
            f"{self.agent_type} - "
            f"{self.workflow_run_id} - "
            f"Attempt {self.attempt} ({self.status})"
        )