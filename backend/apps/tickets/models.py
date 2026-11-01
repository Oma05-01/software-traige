import uuid

from django.db import models


class Ticket(models.Model):

    class Category(models.TextChoices):
        UNCLASSIFIED = "unclassified", "Unclassified"
        BUG = "bug", "Bug"
        FEATURE = "feature", "Feature Request"
        SPAM = "spam", "Spam"
        OTHER = "other", "Other"

    class Priority(models.TextChoices):
        UNASSESSED = "unassessed", "Unassessed"
        LOW = "low", "Low"
        MEDIUM = "medium", "Medium"
        HIGH = "high", "High"
        CRITICAL = "critical", "Critical"

    class Status(models.TextChoices):
        SUBMITTED = "submitted", "Submitted"
        IN_PROGRESS = "in_progress", "In Progress"
        AWAITING_REVIEW = "awaiting_review", "Awaiting Review"
        COMPLETED = "completed", "Completed"
        CLOSED = "closed", "Closed"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    # Submitted information
    title = models.CharField(max_length=180)

    description = models.TextField()

    reporter_name = models.CharField(
        max_length=120,
        blank=True,
    )

    reporter_email = models.EmailField()

    environment = models.TextField(blank=True)

    steps_to_reproduce = models.TextField(blank=True)

    expected_behavior = models.TextField(blank=True)

    actual_behavior = models.TextField(blank=True)

    # System-managed classification
    category = models.CharField(
        max_length=20,
        choices=Category.choices,
        default=Category.UNCLASSIFIED,
        db_index=True,
    )

    priority = models.CharField(
        max_length=20,
        choices=Priority.choices,
        default=Priority.UNASSESSED,
        db_index=True,
    )

    # Overall ticket lifecycle
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.SUBMITTED,
        db_index=True,
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["status", "created_at"],
                name="ticket_status_created_idx",
            ),
        ]

    def __str__(self):
        return f"{self.title} ({self.id})"