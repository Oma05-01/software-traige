from django.test import TestCase

from apps.tickets.models import Ticket
from apps.agents.implementations.receptionist import (
    classify_ticket,
)


class ReceptionistClassificationTests(TestCase):

    def create_ticket(self, **overrides):
        data = {
            "title": "PDF upload failure",
            "description": (
                "The application crashes when uploading "
                "PDF files larger than 25 MB."
            ),
            "reporter_email": "reporter@example.com",
            "environment": "Windows 11, Chrome",
        }

        data.update(overrides)

        return Ticket.objects.create(**data)

    def test_identifies_bug_report(self):
        ticket = self.create_ticket()

        result = classify_ticket(ticket)

        self.assertEqual(
            result["category"],
            Ticket.Category.BUG,
        )

        self.assertEqual(
            result["priority"],
            Ticket.Priority.HIGH,
        )

    def test_identifies_feature_request(self):
        ticket = self.create_ticket(
            title="CSV export",
            description=(
                "I would like the application to support "
                "CSV exports."
            ),
        )

        result = classify_ticket(ticket)

        self.assertEqual(
            result["category"],
            Ticket.Category.FEATURE,
        )

        self.assertEqual(
            result["priority"],
            Ticket.Priority.MEDIUM,
        )

    def test_identifies_critical_issue(self):
        ticket = self.create_ticket(
            title="Production outage",
            description="The production service is down.",
        )

        result = classify_ticket(ticket)

        self.assertEqual(
            result["priority"],
            Ticket.Priority.CRITICAL,
        )

    def test_identifies_low_priority_issue(self):
        ticket = self.create_ticket(
            title="Minor UI typo",
            description="There is a typo in the dashboard.",
        )

        result = classify_ticket(ticket)

        self.assertEqual(
            result["priority"],
            Ticket.Priority.LOW,
        )

    def test_ambiguous_report_requires_human_review(self):
        ticket = self.create_ticket(
            title="CSV export",
            description=(
                "The export function crashes. "
                "Please add support for CSV exports."
            ),
        )

        result = classify_ticket(ticket)

        self.assertEqual(
            result["category"],
            Ticket.Category.OTHER,
        )

        self.assertTrue(
            result["needs_human_review"]
        )

    def test_unclear_report_is_not_forced_into_category(self):
        ticket = self.create_ticket(
            title="Application question",
            description="I would like some information.",
        )

        result = classify_ticket(ticket)

        self.assertEqual(
            result["category"],
            Ticket.Category.OTHER,
        )

        self.assertEqual(
            result["priority"],
            Ticket.Priority.UNASSESSED,
        )

        self.assertTrue(
            result["needs_human_review"]
        )

    def test_extracts_technical_details(self):
        ticket = self.create_ticket()

        result = classify_ticket(ticket)

        details = result["technical_details"]

        self.assertIn("PDF", details["file_types"])

        self.assertIn("25 MB", details["file_sizes"])

        self.assertEqual(
            details["environment"],
            "Windows 11, Chrome",
        )

    def test_result_contains_classifier_version(self):
        ticket = self.create_ticket()

        result = classify_ticket(ticket)

        self.assertEqual(
            result["classifier"]["name"],
            "deterministic_receptionist",
        )

        self.assertEqual(
            result["classifier"]["version"],
            "1.0.0",
        )