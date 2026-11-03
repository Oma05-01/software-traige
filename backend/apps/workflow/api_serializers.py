from rest_framework import serializers

from apps.agents.models import AgentExecution
from apps.events.models import WorkflowEvent
from apps.workflow.models import WorkflowRun


class AgentExecutionReadSerializer(serializers.ModelSerializer):

    class Meta:
        model = AgentExecution
        fields = [
            "id",
            "agent_type",
            "status",
            "attempt",
            "output_payload",
            "started_at",
            "finished_at",
            "error_code",
            "error_message",
            "created_at",
            "updated_at",
        ]


class WorkflowEventReadSerializer(serializers.ModelSerializer):

    class Meta:
        model = WorkflowEvent
        fields = [
            "id",
            "event_type",
            "source",
            "payload",
            "created_at",
        ]


class WorkflowReadSerializer(serializers.ModelSerializer):

    agent_executions = AgentExecutionReadSerializer(
        many=True,
        read_only=True,
    )

    events = WorkflowEventReadSerializer(
        many=True,
        read_only=True,
    )

    class Meta:
        model = WorkflowRun
        fields = [
            "id",
            "ticket",
            "status",
            "current_stage",
            "workflow_version",
            "started_at",
            "finished_at",
            "error_code",
            "error_message",
            "created_at",
            "updated_at",
            "agent_executions",
            "events",
        ]