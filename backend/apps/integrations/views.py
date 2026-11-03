from django.shortcuts import get_object_or_404
from apps.reviews.models import ReviewRequest
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.generics import RetrieveAPIView
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.integrations.models import ActionExecution
from apps.integrations.serializers import ActionExecutionSerializer
from apps.integrations.services import (
    ActionNotAuthorized,
    ActionExecutionNotReady,
    queue_action_execution,
)


class QueueApprovedActionView(APIView):
    """
    Request execution of an approved review action.

    This endpoint only accepts staff requests.
    """

    permission_classes = [IsAdminUser]

    def post(self, request, review_id):
        get_object_or_404(
            ReviewRequest,
            pk=review_id,
        )

        try:
            execution = queue_action_execution(review_id)

        except ActionNotAuthorized as exc:
            raise ValidationError({"detail": str(exc)})

        except ActionExecutionNotReady as exc:
            raise ValidationError({"detail": str(exc)})

        response_status = (
            status.HTTP_200_OK
            if execution.status in (
                ActionExecution.Status.RUNNING,
                ActionExecution.Status.SUCCEEDED,
            )
            else status.HTTP_202_ACCEPTED
        )

        return Response(
            ActionExecutionSerializer(execution).data,
            status=response_status,
        )

class ActionExecutionDetailView(RetrieveAPIView):

    serializer_class = ActionExecutionSerializer
    permission_classes = [IsAdminUser]

    def get_queryset(self):
        return ActionExecution.objects.select_related(
            "review_request",
        )