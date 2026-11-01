from django.test import TestCase

from .models import Ticket
from .services import (
    InvalidTicketTransition,
    transition_ticket,
)


class TicketTransitionTests(TestCase):

    def setUp(self):
        self.ticket = Ticket.objects.create(
            title="PDF upload failure",
            description="Upload crashes above 25 MB.",
            reporter_email="reporter@example.com",
        )

    def test_submitted_to_in_progress(self):
        ticket = transition_ticket(
            self.ticket.id,
            Ticket.Status.IN_PROGRESS,
        )

        self.assertEqual(
            ticket.status,
            Ticket.Status.IN_PROGRESS,
        )

    def test_in_progress_to_awaiting_review(self):
        transition_ticket(
            self.ticket.id,
            Ticket.Status.IN_PROGRESS,
        )

        ticket = transition_ticket(
            self.ticket.id,
            Ticket.Status.AWAITING_REVIEW,
        )

        self.assertEqual(
            ticket.status,
            Ticket.Status.AWAITING_REVIEW,
        )

    def test_awaiting_review_can_be_rejected_for_revision(self):
        transition_ticket(
            self.ticket.id,
            Ticket.Status.IN_PROGRESS,
        )

        transition_ticket(
            self.ticket.id,
            Ticket.Status.AWAITING_REVIEW,
        )

        ticket = transition_ticket(
            self.ticket.id,
            Ticket.Status.IN_PROGRESS,
        )

        self.assertEqual(
            ticket.status,
            Ticket.Status.IN_PROGRESS,
        )

    def test_invalid_transition_is_rejected(self):
        with self.assertRaises(InvalidTicketTransition):
            transition_ticket(
                self.ticket.id,
                Ticket.Status.COMPLETED,
            )

        self.ticket.refresh_from_db()

        self.assertEqual(
            self.ticket.status,
            Ticket.Status.SUBMITTED,
        )

    def test_repeated_transition_is_idempotent(self):
        first = transition_ticket(
            self.ticket.id,
            Ticket.Status.IN_PROGRESS,
        )

        second = transition_ticket(
            self.ticket.id,
            Ticket.Status.IN_PROGRESS,
        )

        self.assertEqual(first.id, second.id)
        self.assertEqual(
            second.status,
            Ticket.Status.IN_PROGRESS,
        )

    def test_closed_ticket_cannot_be_reopened(self):
        transition_ticket(
            self.ticket.id,
            Ticket.Status.CLOSED,
        )

        with self.assertRaises(InvalidTicketTransition):
            transition_ticket(
                self.ticket.id,
                Ticket.Status.IN_PROGRESS,
            )

    def test_unknown_status_is_rejected(self):
        with self.assertRaises(ValueError):
            transition_ticket(
                self.ticket.id,
                "something_invalid",
            )