
from types import SimpleNamespace
from unittest.mock import patch


from celery.exceptions import Retry
from django.test import TestCase

from apps.agents.llm.base import (
    LLMRequestError,
    LLMTransientError,
)
from apps.agents.retry_policy import (
    handle_transient_agent_failure,
)
from apps.agents.tasks import (
    process_debugger_workflow,
    process_product_manager_workflow,
    process_support_rep_workflow,
    process_ticket_workflow,
    _is_redelivered
)
from apps.agents.models import AgentExecution
from apps.events.models import WorkflowEvent
from apps.tickets.models import Ticket
from apps.workflow.models import WorkflowRun
from apps.workflow.services import (
    create_workflow_for_ticket,
    transition_workflow,
)


class AgentCeleryRetryTests(TestCase):

    def setUp(self):
        self.ticket = Ticket.objects.create(
            title="PDF upload failure",
            description=(
                "The application crashes when uploading "
                "large PDF files."
            ),
            reporter_email="reporter@example.com",
            environment="Windows 11, Chrome",
        )

        self.workflow = create_workflow_for_ticket(
            self.ticket.id,
        )

    def _prepare_running_stage(self, stage, category=None):
        self.workflow = transition_workflow(
            self.workflow.id,
            WorkflowRun.Status.RUNNING,
        )

        self.workflow.current_stage = stage
        self.workflow.save(
            update_fields=["current_stage"],
        )

        if category is not None:
            self.ticket.category = category
            self.ticket.save(
                update_fields=["category"],
            )


    def _invoke_task(self, task, retries, delivery_info=None):
        task.push_request(
            id="celery-retry-test-id",
            retries=retries,
            delivery_info=delivery_info or {},
        )

        try:
            return task.run(str(self.workflow.id))
        finally:
            task.pop_request()


    def _assert_redelivery_flag_forwarded(
        self,
        task,
        runner_path,
        stage=None,
        category=None,
    ):
        if stage is not None:
            self._prepare_running_stage(stage, category)

        fake_execution = SimpleNamespace(
            id="fake-agent-execution-id",
            status=AgentExecution.Status.FAILED,
        )

        with patch(
            runner_path,
            return_value=fake_execution,
        ) as runner_mock:

            for redelivered in (True, False):
                self._invoke_task(
                    task,
                    retries=0,
                    delivery_info={
                        "redelivered": redelivered,
                    },
                )

        self.assertEqual(
            [
                call.kwargs["redelivered"]
                for call in runner_mock.call_args_list
            ],
            [True, False],
        )

        self.assertEqual(runner_mock.call_count, 2)


    def _assert_retry_scheduled(
        self,
        task,
        runner_path,
        retries,
        expected_delay,
    ):
        error = LLMTransientError(
            "Simulated temporary provider failure."
        )

        with patch(runner_path, side_effect=error):
            with patch.object(
                task,
                "retry",
                side_effect=Retry(),
            ) as retry_mock:

                with self.assertRaises(Retry):
                    self._invoke_task(task, retries)

        retry_mock.assert_called_once()

        self.assertEqual(
            retry_mock.call_args.kwargs["countdown"],
            expected_delay,
        )

        self.assertEqual(
            retry_mock.call_args.kwargs["max_retries"],
            2,
        )

        event = WorkflowEvent.objects.get(
            workflow_run=self.workflow,
            event_type="workflow.agent_retry_scheduled",
        )

        self.assertEqual(
            event.payload["retry_number"],
            retries + 1,
        )

        self.assertEqual(
            event.payload["countdown_seconds"],
            expected_delay,
        )

        self.workflow.refresh_from_db()

        self.assertEqual(
            self.workflow.status,
            WorkflowRun.Status.RUNNING,
        )

    def test_receptionist_schedules_first_retry(self):
        self._assert_retry_scheduled(
            task=process_ticket_workflow,
            runner_path="apps.agents.tasks.run_receptionist",
            retries=0,
            expected_delay=30,
        )

    def test_debugger_schedules_second_retry(self):
        self._prepare_running_stage(
            WorkflowRun.Stage.DEBUGGER,
            Ticket.Category.BUG,
        )

        self._assert_retry_scheduled(
            task=process_debugger_workflow,
            runner_path="apps.agents.tasks.run_debugger",
            retries=1,
            expected_delay=60,
        )

    def test_support_rep_uses_shared_retry_policy(self):
        self._prepare_running_stage(
            WorkflowRun.Stage.SUPPORT_REP,
            Ticket.Category.BUG,
        )

        self._assert_retry_scheduled(
            task=process_support_rep_workflow,
            runner_path="apps.agents.tasks.run_support_rep",
            retries=0,
            expected_delay=30,
        )

    def test_product_manager_uses_shared_retry_policy(self):
        self._prepare_running_stage(
            WorkflowRun.Stage.PRODUCT_MANAGER,
            Ticket.Category.FEATURE,
        )

        self._assert_retry_scheduled(
            task=process_product_manager_workflow,
            runner_path="apps.agents.tasks.run_product_manager",
            retries=0,
            expected_delay=30,
        )

    def test_retry_exhaustion_fails_workflow(self):
        self._prepare_running_stage(
            WorkflowRun.Stage.SUPPORT_REP,
            Ticket.Category.BUG,
        )

        error = LLMTransientError(
            "Simulated persistent provider failure."
        )

        with patch(
            "apps.agents.tasks.run_support_rep",
            side_effect=error,
        ):
            with patch.object(
                process_support_rep_workflow,
                "retry",
            ) as retry_mock:

                with self.assertRaises(LLMTransientError):
                    self._invoke_task(
                        process_support_rep_workflow,
                        retries=2,
                    )

        retry_mock.assert_not_called()

        self.workflow.refresh_from_db()

        self.assertEqual(
            self.workflow.status,
            WorkflowRun.Status.FAILED,
        )

        self.assertEqual(
            self.workflow.error_code,
            "AGENT_RETRY_EXHAUSTED",
        )

        self.assertIsNotNone(
            self.workflow.finished_at,
        )

        event = WorkflowEvent.objects.get(
            workflow_run=self.workflow,
            event_type="workflow.agent_retry_exhausted",
        )

        self.assertEqual(
            event.payload["retries_used"],
            2,
        )

        self.assertEqual(
            event.payload["total_attempts"],
            3,
        )

    def test_permanent_provider_error_does_not_trigger_retry(self):
        error = LLMRequestError(
            "Simulated permanent provider error."
        )

        with patch(
            "apps.agents.tasks.run_receptionist",
            side_effect=error,
        ):
            with patch.object(
                process_ticket_workflow,
                "retry",
            ) as retry_mock:

                with self.assertRaises(LLMRequestError):
                    self._invoke_task(
                        process_ticket_workflow,
                        retries=0,
                    )

        retry_mock.assert_not_called()

        self.assertFalse(
            WorkflowEvent.objects.filter(
                workflow_run=self.workflow,
                event_type="workflow.agent_retry_scheduled",
            ).exists()
        )

    def test_retry_is_skipped_when_agent_stage_has_changed(self):
        self._prepare_running_stage(
            WorkflowRun.Stage.DEBUGGER,
            Ticket.Category.BUG,
        )

        process_support_rep_workflow.push_request(
            id="celery-stale-stage-test",
            retries=0,
        )

        try:
            result = handle_transient_agent_failure(
                task=process_support_rep_workflow,
                workflow_id=self.workflow.id,
                agent_type="support_rep",
                exc=LLMTransientError(
                    "Simulated temporary provider failure."
                ),
            )
        finally:
            process_support_rep_workflow.pop_request()

        self.assertFalse(result)

        self.assertFalse(
            WorkflowEvent.objects.filter(
                workflow_run=self.workflow,
                event_type="workflow.agent_retry_scheduled",
            ).exists()
        )

        self.workflow.refresh_from_db()

        self.assertEqual(
            self.workflow.status,
            WorkflowRun.Status.RUNNING,
        )


    def test_redelivery_detector_defaults_to_false(self):
        task = SimpleNamespace(
            request=SimpleNamespace(delivery_info=None)
        )

        self.assertFalse(_is_redelivered(task))


    def test_receptionist_task_forwards_redelivery_flag(self):
        self._assert_redelivery_flag_forwarded(
            task=process_ticket_workflow,
            runner_path="apps.agents.tasks.run_receptionist",
        )


    def test_debugger_task_forwards_redelivery_flag(self):
        self._assert_redelivery_flag_forwarded(
            task=process_debugger_workflow,
            runner_path="apps.agents.tasks.run_debugger",
            stage=WorkflowRun.Stage.DEBUGGER,
            category=Ticket.Category.BUG,
        )


    def test_support_rep_task_forwards_redelivery_flag(self):
        self._assert_redelivery_flag_forwarded(
            task=process_support_rep_workflow,
            runner_path="apps.agents.tasks.run_support_rep",
            stage=WorkflowRun.Stage.SUPPORT_REP,
            category=Ticket.Category.BUG,
        )


    def test_product_manager_task_forwards_redelivery_flag(self):
        self._assert_redelivery_flag_forwarded(
            task=process_product_manager_workflow,
            runner_path="apps.agents.tasks.run_product_manager",
            stage=WorkflowRun.Stage.PRODUCT_MANAGER,
            category=Ticket.Category.FEATURE,
        )
