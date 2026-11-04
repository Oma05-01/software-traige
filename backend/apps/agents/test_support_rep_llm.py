
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import SimpleTestCase

from apps.agents.implementations.support_rep_llm import (
    draft_support_response_llm,
)


class SupportRepLLMTests(SimpleTestCase):

    def setUp(self):
        self.ticket = SimpleNamespace(
            title="Report generation behaves unexpectedly",
            description=(
                "I am having trouble generating reports. "
                "Sometimes the results are different from "
                "what I expect."
            ),
            reporter_name="Test Reporter",
            environment="Windows 11, Chrome",
            steps_to_reproduce="Open reports and generate a report.",
            expected_behavior="The report should generate correctly.",
            actual_behavior="The report produces unexpected results.",
        )

        self.receptionist_findings = {
            "category": "bug",
            "priority": "medium",
            "classification_confidence": "high",
        }

        self.debugger_findings = {
            "investigation_status": "no_relevant_evidence",
            "documented_evidence": [],
            "root_cause": {
                "status": "not_established",
                "explanation": "No root cause has been established.",
            },
            "possible_explanations": [],
            "recommended_workaround": None,
        }

        self.product_manager_findings = {
            "problem_statement": (
                "Users need an easier way to export reports."
            ),
            "requested_capability": (
                "Add CSV export functionality."
            ),
            "user_value": (
                "Users can process report data in spreadsheet tools."
            ),
            "proposed_scope": (
                "Allow report data to be exported as CSV."
            ),
            "acceptance_criteria": [
                "Users can export report data as CSV."
            ],
            "considerations": [],
            "open_questions": [],
            "assessment_confidence": "medium",
        }

    def generate_response(
        self,
        *,
        product_manager_findings=None,
        acknowledgement=None,
        follow_up_questions=None,
    ):
        """Run the response builder with a mocked LLM provider."""

        provider = Mock()
        provider.provider_name = "groq"
        provider.model_name = "openai/gpt-oss-20b"

        provider.generate_structured.return_value = {
            "acknowledgement": (
                acknowledgement
                or "Thank you for explaining the situation."
            ),
            "follow_up_questions": (
                follow_up_questions or []
            ),
        }

        with (
            patch(
                "apps.agents.implementations.support_rep_llm.get_llm_provider",
                return_value=provider,
            ),
            patch(
                "apps.agents.implementations.support_rep_llm._build_evidence_references",
                return_value=[],
            ),
            patch(
                "apps.agents.implementations.support_rep_llm._build_internal_review_notes",
                return_value=[],
            ),
        ):
            result = draft_support_response_llm(
                ticket=self.ticket,
                receptionist_findings=self.receptionist_findings,
                debugger_findings=(
                    None
                    if product_manager_findings is not None
                    else self.debugger_findings
                ),
                product_manager_findings=product_manager_findings,
            )

        provider.generate_structured.assert_called_once()

        return result

    def test_bug_report_uses_issue_acknowledgement(self):
        result = self.generate_response(
            follow_up_questions=[
                "Which version of the application are you using?"
            ],
        )

        response = result["draft_response"]

        self.assertIn(
            "Thank you for reporting this issue.",
            response,
        )

        self.assertIn(
            "To help us investigate further",
            response,
        )

        self.assertIn(
            "Thank you for helping us investigate this issue.",
            response,
        )

        self.assertNotIn(
            "Thank you for sharing your feature suggestion.",
            response,
        )

        self.assertEqual(
            result["response_type"],
            "acknowledgement_and_information_request",
        )

    def test_feature_request_uses_feature_acknowledgement(self):
        result = self.generate_response(
            product_manager_findings=self.product_manager_findings,
            follow_up_questions=[
                "Could you explain what problem this feature solves?"
            ],
        )

        response = result["draft_response"]

        self.assertIn(
            "Thank you for sharing your feature suggestion.",
            response,
        )

        self.assertIn(
            "initial assessment of your suggestion",
            response,
        )

        self.assertIn(
            "To help us assess your suggestion",
            response,
        )

        self.assertIn(
            "Your clarification will help us understand "
            "the capability you're requesting.",
            response,
        )

        self.assertNotIn(
            "Thank you for reporting this issue.",
            response,
        )

        self.assertNotIn(
            "We will review the additional information before "
            "recommending a solution.",
            response,
        )

        self.assertEqual(
            result["response_type"],
            "feature_request_acknowledgement",
        )

    def test_feature_request_without_questions_uses_short_closing(self):
        result = self.generate_response(
            product_manager_findings=self.product_manager_findings,
            follow_up_questions=[],
        )

        response = result["draft_response"]

        self.assertIn(
            "Thank you for taking the time to share your feedback.",
            response,
        )

        self.assertNotIn(
            "Your clarification will help us understand",
            response,
        )

    def test_response_does_not_duplicate_greeting_closing_or_signature(self):
        result = self.generate_response(
            follow_up_questions=[
                "Which version of the application are you using?"
            ],
        )

        response = result["draft_response"]

        self.assertEqual(response.count("Hello Test Reporter,"), 1)
        self.assertEqual(response.count("Regards,"), 1)
        self.assertEqual(response.count("Support Team"), 1)

        self.assertEqual(
            response.count(
                "Thank you for helping us investigate this issue."
            ),
            1,
        )

    def test_feature_response_preserves_product_assessment(self):
        result = self.generate_response(
            product_manager_findings=self.product_manager_findings,
        )

        assessment = result["product_assessment"]

        self.assertEqual(
            assessment["requested_capability"],
            "Add CSV export functionality.",
        )

        self.assertEqual(
            assessment["assessment_confidence"],
            "medium",
        )

    def test_draft_requires_human_review(self):
        result = self.generate_response()

        self.assertEqual(
            result["draft_status"],
            "pending_human_review",
        )

        self.assertTrue(
            result["requires_human_review"]
        )

        self.assertFalse(
            result["external_send_authorized"]
        )

    def test_responder_records_llm_provider_and_version(self):
        result = self.generate_response()

        self.assertEqual(
            result["responder"]["name"],
            "groq_support_rep",
        )

        self.assertEqual(
            result["responder"]["provider"],
            "groq",
        )

        self.assertEqual(
            result["responder"]["model"],
            "openai/gpt-oss-20b",
        )

        self.assertEqual(
            result["responder"]["version"],
            "1.1.0",
        )
