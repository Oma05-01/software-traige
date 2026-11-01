from rest_framework.test import APITestCase

from apps.tickets.models import Ticket
from apps.workflow.models import WorkflowRun
from apps.agents.models import AgentExecution
from apps.events.models import WorkflowEvent
from apps.reviews.models import ReviewRequest
from django.test import override_settings

@override_settings(
    CELERY_TASK_ALWAYS_EAGER=True,
    CELERY_TASK_EAGER_PROPAGATES=True,
)
class TicketSubmissionWorkflowTests(APITestCase):

    def setUp(self):
        self.url = "/api/tickets/"

    def submit_ticket(self, payload):
        # TestCase wraps tests in a transaction, so explicitly
        # execute callbacks registered with transaction.on_commit.
        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            response = self.client.post(
                self.url,
                payload,
                format="json",
            )

        self.assertEqual(len(callbacks), 1)

        return response

    def test_bug_submission_executes_agent_pipeline_and_awaits_review(self):
        payload = {
            "title": "PDF upload failure",
            "description": (
                "The application crashes when uploading "
                "PDF files larger than 25 MB."
            ),
            "reporter_email": "reporter@example.com",
            "environment": "Windows 11, Chrome",
        }

        response = self.submit_ticket(payload)

        self.assertEqual(response.status_code, 201)

        ticket = Ticket.objects.get(
            reporter_email="reporter@example.com"
        )

        workflow = WorkflowRun.objects.get(ticket=ticket)

        # Retrieve each agent execution.
        receptionist_execution = AgentExecution.objects.get(
            workflow_run=workflow,
            agent_type=AgentExecution.AgentType.RECEPTIONIST,
        )

        debugger_execution = AgentExecution.objects.get(
            workflow_run=workflow,
            agent_type=AgentExecution.AgentType.DEBUGGER,
        )

        support_rep_execution = AgentExecution.objects.get(
            workflow_run=workflow,
            agent_type=AgentExecution.AgentType.SUPPORT_REP,
        )

        # Verify each agent has its own Celery task.
        self.assertTrue(receptionist_execution.celery_task_id)
        self.assertTrue(debugger_execution.celery_task_id)
        self.assertTrue(support_rep_execution.celery_task_id)

        self.assertEqual(
            len({
                receptionist_execution.celery_task_id,
                debugger_execution.celery_task_id,
                support_rep_execution.celery_task_id,
            }),
            3,
        )

        review_request = ReviewRequest.objects.get(
        agent_execution=support_rep_execution,
        action_type=ReviewRequest.ActionType.SEND_SUPPORT_RESPONSE,
        )

        self.assertEqual(
            review_request.status,
            ReviewRequest.Status.PENDING,
        )

        self.assertEqual(
            review_request.workflow_run,
            workflow,
        )

        # Verify successful execution.
        for execution in [
            receptionist_execution,
            debugger_execution,
            support_rep_execution,
        ]:
            self.assertEqual(
                execution.status,
                AgentExecution.Status.SUCCEEDED,
            )

        # Verify Receptionist classification.
        self.assertEqual(
            ticket.category,
            Ticket.Category.BUG,
        )

        self.assertEqual(
            ticket.priority,
            Ticket.Priority.HIGH,
        )

        # Verify Support Rep created a draft, not a sent message.
        draft = support_rep_execution.output_payload

        self.assertEqual(
            draft["draft_status"],
            "pending_human_review",
        )

        self.assertTrue(
            draft["requires_human_review"]
        )

        self.assertFalse(
            draft["external_send_authorized"]
        )

        self.assertTrue(
            draft["draft_response"]
        )

        # Refresh objects to verify final persisted state.
        workflow.refresh_from_db()
        ticket.refresh_from_db()

        self.assertEqual(
            workflow.status,
            WorkflowRun.Status.AWAITING_REVIEW,
        )

        self.assertEqual(
            workflow.current_stage,
            WorkflowRun.Stage.HUMAN_REVIEW,
        )

        self.assertEqual(
            ticket.status,
            Ticket.Status.AWAITING_REVIEW,
        )

        self.assertEqual(
            response.data["workflow_id"],
            str(workflow.id),
        )

    def test_feature_submission_routes_to_product_manager(self):
        payload = {
            "title": "CSV export support",
            "description": "Please add support for CSV exports.",
            "reporter_email": "feature@example.com",
        }

        response = self.submit_ticket(payload)

        self.assertEqual(response.status_code, 201)

        ticket = Ticket.objects.get(
            reporter_email="feature@example.com"
        )

        workflow = WorkflowRun.objects.get(ticket=ticket)

        self.assertEqual(
            ticket.category,
            Ticket.Category.FEATURE,
        )

        self.assertEqual(
            workflow.current_stage,
            WorkflowRun.Stage.PRODUCT_MANAGER,
        )

        self.assertEqual(
            workflow.status,
            WorkflowRun.Status.RUNNING,
        )

    def test_unclear_submission_enters_human_review(self):
        payload = {
            "title": "Application question",
            "description": "I would like some information.",
            "reporter_email": "unclear@example.com",
        }

        response = self.submit_ticket(payload)

        self.assertEqual(response.status_code, 201)

        ticket = Ticket.objects.get(
            reporter_email="unclear@example.com"
        )

        workflow = WorkflowRun.objects.get(ticket=ticket)

        execution = AgentExecution.objects.get(
            workflow_run=workflow,
        )

        self.assertEqual(
            ticket.category,
            Ticket.Category.OTHER,
        )

        self.assertEqual(
            ticket.status,
            Ticket.Status.AWAITING_REVIEW,
        )

        self.assertEqual(
            workflow.status,
            WorkflowRun.Status.AWAITING_REVIEW,
        )

        self.assertEqual(
            workflow.current_stage,
            WorkflowRun.Stage.HUMAN_REVIEW,
        )

        self.assertEqual(
            execution.status,
            AgentExecution.Status.SUCCEEDED,
        )

        self.assertTrue(
            WorkflowEvent.objects.filter(
                workflow_run=workflow,
                event_type="agent.classification_completed",
            ).exists()
        )