from rest_framework.test import APITestCase

from apps.tickets.models import Ticket
from apps.workflow.models import WorkflowRun
from apps.agents.models import AgentExecution
from apps.events.models import WorkflowEvent

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

    def test_bug_submission_executes_receptionist(self):
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

        execution = AgentExecution.objects.get(
            workflow_run=workflow,
            agent_type=AgentExecution.AgentType.RECEPTIONIST,
        )

        self.assertTrue(execution.celery_task_id)

        self.assertEqual(
            execution.status,
            AgentExecution.Status.SUCCEEDED,
        )

        self.assertEqual(
            ticket.category,
            Ticket.Category.BUG,
        )

        self.assertEqual(
            ticket.priority,
            Ticket.Priority.HIGH,
        )

        self.assertEqual(
            workflow.status,
            WorkflowRun.Status.RUNNING,
        )

        self.assertEqual(
            workflow.current_stage,
            WorkflowRun.Stage.DEBUGGER,
        )

        self.assertEqual(
            ticket.status,
            Ticket.Status.IN_PROGRESS,
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