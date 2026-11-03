import uuid

from django.db import models
from django.db.models import Q


class ActionExecution(models.Model):

    class ActionType(models.TextChoices):
        SEND_SUPPORT_RESPONSE = (
            "send_support_response",
            "Send support response",
        )
        CREATE_GITHUB_ISSUE = (
            "create_github_issue",
            "Create GitHub issue",
        )

    class Provider(models.TextChoices):
        MOCK_EMAIL = "mock_email", "Mock email provider"

    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        RUNNING = "running", "Running"
        SUCCEEDED = "succeeded", "Succeeded"
        FAILED = "failed", "Failed"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    # One approved review request can have only one execution record.
    # Retries, when deliberately enabled later, will reuse this record.
    review_request = models.OneToOneField(
        "reviews.ReviewRequest",
        on_delete=models.PROTECT,
        related_name="action_execution",
    )

    action_type = models.CharField(
        max_length=50,
        choices=ActionType.choices,
    )

    provider = models.CharField(
        max_length=50,
        choices=Provider.choices,
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.QUEUED,
    )

    # Deterministic key used to identify duplicate action requests.
    idempotency_key = models.CharField(
        max_length=255,
        unique=True,
    )

    # Frozen snapshot of the approved action, including its recipient.
    request_payload = models.JSONField(default=dict)

    provider_response = models.JSONField(default=dict)

    attempt_count = models.PositiveSmallIntegerField(default=0)

    started_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    finished_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    error_code = models.CharField(
        max_length=100,
        blank=True,
    )

    error_message = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(
                        status="queued",
                        started_at__isnull=True,
                        finished_at__isnull=True,
                        attempt_count=0,
                    )
                    |
                    Q(
                        status="running",
                        started_at__isnull=False,
                        finished_at__isnull=True,
                        attempt_count__gte=1,
                    )
                    |
                    Q(
                        status__in=["succeeded", "failed"],
                        started_at__isnull=False,
                        finished_at__isnull=False,
                        attempt_count__gte=1,
                    )
                ),
                name="action_execution_state_consistent",
            ),
        ]

        indexes = [
            models.Index(
                fields=["status", "created_at"],
                name="action_status_created_idx",
            ),
        ]

    def __str__(self):
        return f"{self.action_type} - {self.status}"