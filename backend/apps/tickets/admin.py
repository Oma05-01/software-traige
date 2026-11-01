from django.contrib import admin

from .models import Ticket


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):

    list_display = (
        "title",
        "category",
        "priority",
        "status",
        "reporter_email",
        "created_at",
    )

    list_filter = (
        "category",
        "priority",
        "status",
        "created_at",
    )

    search_fields = (
        "title",
        "description",
        "reporter_email",
    )

    readonly_fields = (
        "id",
        "created_at",
        "updated_at",
    )