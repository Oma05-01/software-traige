from rest_framework import serializers

from apps.reviews.models import ReviewRequest
from apps.reviews.models import ClassificationReview
from apps.tickets.models import Ticket

class ReviewRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReviewRequest
        fields = [
            "id",
            "workflow_run",
            "agent_execution",
            "action_type",
            "status",
            "proposed_payload",
            "reviewed_by",
            "reviewed_at",
            "decision_note",
            "created_at",
            "updated_at",
            "revision_number",
        ]
        read_only_fields = fields


class ReviewProposalUpdateSerializer(serializers.Serializer):
    proposed_payload = serializers.JSONField()

    def validate_proposed_payload(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError(
                "The proposed payload must be a JSON object."
            )

        return value


class ReviewDecisionSerializer(serializers.Serializer):
    decision_note = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=2000,
        trim_whitespace=True,
    )

class ReviewChangesRequestSerializer(serializers.Serializer):
    decision_note = serializers.CharField(
        required=True,
        allow_blank=False,
        max_length=2000,
        trim_whitespace=True,
    )

class ClassificationReviewSerializer(serializers.ModelSerializer):
    workflow_run_id = serializers.UUIDField(read_only=True)
    agent_execution_id = serializers.UUIDField(read_only=True)

    ticket_id = serializers.UUIDField(
        source="workflow_run.ticket.id",
        read_only=True,
    )
    ticket_title = serializers.CharField(
        source="workflow_run.ticket.title",
        read_only=True,
    )
    ticket_description = serializers.CharField(
        source="workflow_run.ticket.description",
        read_only=True,
    )
    ticket_environment = serializers.CharField(
        source="workflow_run.ticket.environment",
        read_only=True,
    )
    ticket_steps_to_reproduce = serializers.CharField(
        source="workflow_run.ticket.steps_to_reproduce",
        read_only=True,
    )
    ticket_expected_behavior = serializers.CharField(
        source="workflow_run.ticket.expected_behavior",
        read_only=True,
    )
    ticket_actual_behavior = serializers.CharField(
        source="workflow_run.ticket.actual_behavior",
        read_only=True,
    )

    reviewed_by_username = serializers.CharField(
        source="reviewed_by.username",
        read_only=True,
        allow_null=True,
    )

    class Meta:
        model = ClassificationReview
        fields = [
            "id",
            "workflow_run_id",
            "agent_execution_id",
            "ticket_id",
            "ticket_title",
            "ticket_description",
            "ticket_environment",
            "ticket_steps_to_reproduce",
            "ticket_expected_behavior",
            "ticket_actual_behavior",
            "proposed_category",
            "proposed_priority",
            "classification_confidence",
            "status",
            "decision",
            "resolved_category",
            "resolved_priority",
            "reviewed_by",
            "reviewed_by_username",
            "reviewed_at",
            "decision_note",
            "created_at",
            "updated_at",
        ]


class ClassificationReviewResolutionSerializer(serializers.Serializer):
    resolved_category = serializers.ChoiceField(
        choices=[
            (Ticket.Category.BUG, "Bug"),
            (Ticket.Category.FEATURE, "Feature Request"),
        ],
    )

    resolved_priority = serializers.ChoiceField(
        choices=[
            (Ticket.Priority.LOW, "Low"),
            (Ticket.Priority.MEDIUM, "Medium"),
            (Ticket.Priority.HIGH, "High"),
            (Ticket.Priority.CRITICAL, "Critical"),
        ],
    )

    decision_note = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=2000,
        default="",
    )