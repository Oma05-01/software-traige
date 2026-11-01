from django.contrib import admin

from .models import AgentExecution


@admin.register(AgentExecution)
class AgentExecutionAdmin(admin.ModelAdmin):

    list_display = (
        "agent_type",
        "workflow_run",
        "attempt",
        "status",
        "started_at",
        "finished_at",
        "created_at",
    )

    list_filter = (
        "agent_type",
        "status",
        "created_at",
    )

    search_fields = (
        "celery_task_id",
        "error_code",
        "workflow_run__id",
    )

    readonly_fields = (
        "id",
        "created_at",
        "updated_at",
        "started_at",
        "finished_at",
    )