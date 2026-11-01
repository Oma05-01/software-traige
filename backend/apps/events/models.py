import uuid

from django.db import models

from apps.workflow.models import WorkflowRun


class WorkflowEvent(models.Model):

    class Source(models.TextChoices):
        SYSTEM = "system", "System"
        AGENT = "agent", "Agent"
        HUMAN = "human", "Human"
        INTEGRATION = "integration", "Integration"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    workflow_run = models.ForeignKey(
        WorkflowRun,
        on_delete=models.PROTECT,
        related_name="events",
    )

    event_type = models.CharField(max_length=100)

    source = models.CharField(
        max_length=20,
        choices=Source.choices,
        default=Source.SYSTEM,
    )

    payload = models.JSONField(default=dict)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]

        indexes = [
            models.Index(
                fields=["workflow_run", "created_at"],
                name="workflow_event_time_idx",
            ),
            models.Index(
                fields=["event_type", "created_at"],
                name="event_type_time_idx",
            ),
        ]

    def __str__(self):
        return (
            f"{self.event_type} "
            f"({self.workflow_run_id})"
        )