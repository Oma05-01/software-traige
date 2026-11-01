from rest_framework import generics
from rest_framework.permissions import AllowAny, IsAdminUser
from rest_framework.throttling import ScopedRateThrottle
from django.db import transaction

from apps.workflow.services import start_ticket_workflow

from .models import Ticket
from .serializers import (
    TicketReadSerializer,
    TicketSubmissionSerializer,
)


class TicketListCreateView(generics.ListCreateAPIView):
    """
    POST: Public ticket submission.
    GET: Staff-only ticket listing.
    """

    queryset = Ticket.objects.all()
    throttle_scope = "ticket_submission"

    def get_serializer_class(self):
        if self.request.method == "POST":
            return TicketSubmissionSerializer

        return TicketReadSerializer

    def get_permissions(self):
        if self.request.method == "POST":
            permission_classes = [AllowAny]
        else:
            permission_classes = [IsAdminUser]

        return [
            permission()
            for permission in permission_classes
        ]

    def get_throttles(self):
        if self.request.method == "POST":
            return [ScopedRateThrottle()]

        return []

    def perform_create(self, serializer):
        """
        Save the ticket and initiate its workflow atomically.
        """

        with transaction.atomic():
            ticket = serializer.save()

            start_ticket_workflow(ticket.id)

        # Refresh after the transaction commits.
        # In a normal request, the on_commit callback has
        # now executed and may have updated the ticket.
        ticket.refresh_from_db()


class TicketDetailView(generics.RetrieveAPIView):
    """
    Retrieves an individual ticket.

    Only authenticated staff members can access it.
    """

    queryset = Ticket.objects.all()
    serializer_class = TicketReadSerializer
    permission_classes = [IsAdminUser]