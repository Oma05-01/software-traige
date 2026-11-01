from django.db import transaction

from .models import Ticket


class InvalidTicketTransition(Exception):
    """Raised when a requested ticket transition is invalid."""


ALLOWED_TRANSITIONS = {
    Ticket.Status.SUBMITTED: {
        Ticket.Status.IN_PROGRESS,
        Ticket.Status.CLOSED,
    },

    Ticket.Status.IN_PROGRESS: {
        Ticket.Status.AWAITING_REVIEW,
        Ticket.Status.CLOSED,
    },

    Ticket.Status.AWAITING_REVIEW: {
        Ticket.Status.IN_PROGRESS,
        Ticket.Status.COMPLETED,
        Ticket.Status.CLOSED,
    },

    Ticket.Status.COMPLETED: {
        Ticket.Status.CLOSED,
    },

    Ticket.Status.CLOSED: set(),
}


@transaction.atomic
def transition_ticket(ticket_id, new_status):
    """
    Safely transition a ticket to an allowed status.

    Uses a database row lock to prevent concurrent
    transitions from silently overwriting each other.
    """

    if new_status not in Ticket.Status.values:
        raise ValueError(f"Unknown ticket status: {new_status}")

    ticket = (
        Ticket.objects
        .select_for_update()
        .get(pk=ticket_id)
    )

    current_status = ticket.status

    # Idempotent request
    if current_status == new_status:
        return ticket

    allowed = ALLOWED_TRANSITIONS[current_status]

    if new_status not in allowed:
        raise InvalidTicketTransition(
            f"Cannot transition ticket from "
            f"{current_status} to {new_status}."
        )

    ticket.status = new_status

    ticket.save(
        update_fields=["status", "updated_at"]
    )

    return ticket