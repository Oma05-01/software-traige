from django.shortcuts import get_object_or_404

from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.reviews.models import ReviewRequest
from apps.reviews.serializers import (
    ReviewChangesRequestSerializer,
    ReviewDecisionSerializer,
    ReviewProposalUpdateSerializer,
    ReviewRequestSerializer,
)

from apps.reviews.services import (
    InvalidReviewAction,
    approve_review_request,
    reject_review_request,
    request_review_changes,
    revise_review_request,
    update_review_proposal,
)


def get_review_or_404(review_id):
    return get_object_or_404(
        ReviewRequest.objects.select_related(
            "workflow_run",
            "agent_execution",
            "reviewed_by",
        ),
        pk=review_id,
    )


def handle_review_error(exc):
    """Convert review-service validation failures into HTTP 400 responses."""
    raise ValidationError({
        "detail": str(exc),
    })


class ReviewRequestListView(ListAPIView):
    """
    List review requests for authenticated staff members.

    Defaults to pending requests. Use status=all to include
    approved and rejected requests.
    """

    serializer_class = ReviewRequestSerializer
    permission_classes = [IsAdminUser]

    def get_queryset(self):
        queryset = ReviewRequest.objects.select_related(
            "workflow_run",
            "agent_execution",
            "reviewed_by",
        )

        status_filter = self.request.query_params.get(
            "status",
            ReviewRequest.Status.PENDING,
        )

        valid_statuses = {
            value
            for value, _ in ReviewRequest.Status.choices
        }

        if status_filter != "all":
            if status_filter not in valid_statuses:
                raise ValidationError({
                    "status": "Invalid review status."
                })

            queryset = queryset.filter(status=status_filter)

        action_filter = self.request.query_params.get("action_type")

        valid_actions = {
            value
            for value, _ in ReviewRequest.ActionType.choices
        }

        if action_filter:
            if action_filter not in valid_actions:
                raise ValidationError({
                    "action_type": "Invalid review action type."
                })

            queryset = queryset.filter(
                action_type=action_filter,
            )

        return queryset.order_by("-created_at")


class ReviewRequestDetailView(RetrieveAPIView):
    """Retrieve an individual review request."""

    serializer_class = ReviewRequestSerializer
    permission_classes = [IsAdminUser]
    lookup_field = "pk"

    def get_queryset(self):
        return ReviewRequest.objects.select_related(
            "workflow_run",
            "agent_execution",
            "reviewed_by",
        )


class ReviewProposalUpdateView(APIView):
    """Edit a proposal while its review request is pending."""

    permission_classes = [IsAdminUser]

    def patch(self, request, pk):
        review_request = get_review_or_404(pk)

        serializer = ReviewProposalUpdateSerializer(
            data=request.data,
        )
        serializer.is_valid(raise_exception=True)

        try:
            updated = update_review_proposal(
                review_request.id,
                request.user,
                serializer.validated_data["proposed_payload"],
            )

        except InvalidReviewAction as exc:
            handle_review_error(exc)

        return Response(
            ReviewRequestSerializer(updated).data,
            status=status.HTTP_200_OK,
        )


class ApproveReviewRequestView(APIView):
    """Approve one specific proposed action."""

    permission_classes = [IsAdminUser]

    def post(self, request, pk):
        review_request = get_review_or_404(pk)

        serializer = ReviewDecisionSerializer(
            data=request.data,
        )
        serializer.is_valid(raise_exception=True)

        try:
            approved = approve_review_request(
                review_request.id,
                request.user,
                serializer.validated_data.get(
                    "decision_note",
                    "",
                ),
            )

        except InvalidReviewAction as exc:
            handle_review_error(exc)

        return Response(
            ReviewRequestSerializer(approved).data,
            status=status.HTTP_200_OK,
        )


class RejectReviewRequestView(APIView):
    """Reject one specific proposed action."""

    permission_classes = [IsAdminUser]

    def post(self, request, pk):
        review_request = get_review_or_404(pk)

        serializer = ReviewDecisionSerializer(
            data=request.data,
        )
        serializer.is_valid(raise_exception=True)

        try:
            rejected = reject_review_request(
                review_request.id,
                request.user,
                serializer.validated_data.get(
                    "decision_note",
                    "",
                ),
            )

        except InvalidReviewAction as exc:
            handle_review_error(exc)

        return Response(
            ReviewRequestSerializer(rejected).data,
            status=status.HTTP_200_OK,
        )

class RequestReviewChangesView(APIView):
    """Ask for corrections without rejecting the proposed action."""

    permission_classes = [IsAdminUser]

    def post(self, request, pk):
        review_request = get_review_or_404(pk)

        serializer = ReviewChangesRequestSerializer(
            data=request.data,
        )
        serializer.is_valid(raise_exception=True)

        try:
            updated = request_review_changes(
                review_request.id,
                request.user,
                serializer.validated_data["decision_note"],
            )

        except InvalidReviewAction as exc:
            handle_review_error(exc)

        return Response(
            ReviewRequestSerializer(updated).data,
            status=status.HTTP_200_OK,
        )


class ReviseReviewRequestView(APIView):
    """Submit a revised proposal after changes have been requested."""

    permission_classes = [IsAdminUser]

    def patch(self, request, pk):
        review_request = get_review_or_404(pk)

        serializer = ReviewProposalUpdateSerializer(
            data=request.data,
        )
        serializer.is_valid(raise_exception=True)

        try:
            updated = revise_review_request(
                review_request.id,
                request.user,
                serializer.validated_data["proposed_payload"],
            )

        except InvalidReviewAction as exc:
            handle_review_error(exc)

        return Response(
            ReviewRequestSerializer(updated).data,
            status=status.HTTP_200_OK,
        )

