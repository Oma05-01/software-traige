from rest_framework import serializers

from apps.reviews.models import ReviewRequest


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