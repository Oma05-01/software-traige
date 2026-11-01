from rest_framework import serializers

from .models import Ticket


# Fields controlled by the application, not the reporter.
SYSTEM_MANAGED_FIELDS = frozenset({
    "id",
    "category",
    "priority",
    "status",
    "created_at",
    "updated_at",
    "workflow_id",
})


class TicketSubmissionSerializer(serializers.ModelSerializer):

    workflow_id = serializers.SerializerMethodField()

    class Meta:
        model = Ticket

        fields = (
            "id",
            "title",
            "description",
            "reporter_name",
            "reporter_email",
            "environment",
            "steps_to_reproduce",
            "expected_behavior",
            "actual_behavior",
            "category",
            "priority",
            "status",
            "created_at",
            "updated_at",
            "workflow_id",
        )

        read_only_fields = tuple(SYSTEM_MANAGED_FIELDS)

    def to_internal_value(self, data):
        """
        Reject attempts to submit system-managed fields.
        """

        supplied_fields = SYSTEM_MANAGED_FIELDS.intersection(
            data.keys()
        )

        if supplied_fields:
            raise serializers.ValidationError({
                field: "This field is managed by the system."
                for field in sorted(supplied_fields)
            })

        return super().to_internal_value(data)

    def get_workflow_id(self, obj):
        workflow = (
            obj.workflow_runs
            .order_by("-created_at")
            .only("id")
            .first()
        )

        return str(workflow.id) if workflow else None


class TicketReadSerializer(serializers.ModelSerializer):

    class Meta:
        model = Ticket

        fields = "__all__"
        read_only_fields = (
            "id",
            "title",
            "description",
            "reporter_name",
            "reporter_email",
            "environment",
            "steps_to_reproduce",
            "expected_behavior",
            "actual_behavior",
            "category",
            "priority",
            "status",
            "created_at",
            "updated_at",
        )