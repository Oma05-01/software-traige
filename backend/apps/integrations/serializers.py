from rest_framework import serializers

from apps.integrations.models import ActionExecution


class ActionExecutionSerializer(serializers.ModelSerializer):

    class Meta:
        model = ActionExecution
        fields = [
            "id",
            "review_request",
            "action_type",
            "provider",
            "status",
            "idempotency_key",
            "provider_response",
            "attempt_count",
            "started_at",
            "finished_at",
            "error_code",
            "error_message",
            "created_at",
            "updated_at",
        ]

        read_only_fields = fields