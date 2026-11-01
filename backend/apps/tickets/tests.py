from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from .models import Ticket


class TicketSubmissionTests(APITestCase):

    def setUp(self):
        self.url = "/api/tickets/"

        self.payload = {
            "title": "PDF upload fails",
            "description": (
                "The application crashes when uploading "
                "large PDF documents."
            ),
            "reporter_name": "Test Reporter",
            "reporter_email": "reporter@example.com",
            "environment": "Windows 11, Chrome",
            "steps_to_reproduce": (
                "Select a PDF larger than 25 MB and upload it."
            ),
            "expected_behavior": (
                "The PDF should upload successfully."
            ),
            "actual_behavior": (
                "The application returns an error."
            ),
        }

    def test_public_user_can_submit_ticket(self):
        response = self.client.post(
            self.url,
            self.payload,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        self.assertEqual(Ticket.objects.count(), 1)

        ticket = Ticket.objects.first()

        self.assertEqual(
            ticket.category,
            Ticket.Category.UNCLASSIFIED,
        )

        self.assertEqual(
            ticket.priority,
            Ticket.Priority.UNASSESSED,
        )

        self.assertEqual(
            ticket.status,
            Ticket.Status.SUBMITTED,
        )

    def test_reporter_cannot_assign_system_fields(self):
        malicious_payload = {
            **self.payload,
            "category": "bug",
            "priority": "critical",
            "status": "completed",
        }

        response = self.client.post(
            self.url,
            malicious_payload,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        self.assertEqual(Ticket.objects.count(), 0)

    def test_invalid_email_is_rejected(self):
        payload = {
            **self.payload,
            "reporter_email": "not-an-email",
        }

        response = self.client.post(
            self.url,
            payload,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        self.assertEqual(Ticket.objects.count(), 0)


class TicketAccessTests(APITestCase):

    def setUp(self):
        self.ticket = Ticket.objects.create(
            title="Test ticket",
            description="A sample issue.",
            reporter_email="reporter@example.com",
        )

    def test_anonymous_user_cannot_list_tickets(self):
        response = self.client.get("/api/tickets/")

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_staff_user_can_list_tickets(self):
        User = get_user_model()

        admin = User.objects.create_superuser(
            username="testadmin",
            email="admin@example.com",
            password="TestPassword123!",
        )

        self.client.force_authenticate(user=admin)

        response = self.client.get("/api/tickets/")

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(len(response.data), 1)

    def test_anonymous_user_cannot_retrieve_ticket(self):
        response = self.client.get(
            f"/api/tickets/{self.ticket.id}/"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )