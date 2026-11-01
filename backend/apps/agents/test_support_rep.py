from types import SimpleNamespace

from django.test import SimpleTestCase

from apps.agents.implementations.support_rep import (
    draft_support_response,
)


class SupportRepTests(SimpleTestCase):

    def setUp(self):
        self.ticket = SimpleNamespace(
            title="Frontend hangs during report generation",
            reporter_name="Test Reporter",
            reporter_email="reporter@example.com",
            description=(
                "The dashboard freezes when generating "
                "large reports."
            ),
            environment="Windows 11, Chrome",
            steps_to_reproduce=(
                "Open reports and generate a report "
                "containing 500 records."
            ),
            expected_behavior=(
                "The report should generate successfully."
            ),
            actual_behavior=(
                "The dashboard becomes unresponsive."
            ),
        )

        self.receptionist_findings = {
            "category": "bug",
            "priority": "medium",
        }

        self.debugger_findings = {
            "investigation_status": "no_relevant_evidence",
            "documented_evidence": [],
            "root_cause": {
                "status": "not_established",
                "explanation": (
                    "No root cause has been established."
                ),
            },
            "possible_explanations": [],
            "recommended_workaround": None,
        }

    def test_creates_a_draft_for_human_review(self):
        result = draft_support_response(
            self.ticket,
            self.receptionist_findings,
            self.debugger_findings,
        )

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

    def test_acknowledges_the_reported_behaviour(self):
        result = draft_support_response(
            self.ticket,
            self.receptionist_findings,
            self.debugger_findings,
        )

        self.assertIn(
            "dashboard becomes unresponsive",
            result["draft_response"],
        )

    def test_does_not_invent_a_root_cause(self):
        result = draft_support_response(
            self.ticket,
            self.receptionist_findings,
            self.debugger_findings,
        )

        response = result["draft_response"].lower()

        self.assertIn(
            "not sufficient to identify the underlying cause",
            response,
        )

        self.assertNotIn(
            "the cause is a memory leak",
            response,
        )

    def test_requests_missing_browser_version(self):
        result = draft_support_response(
            self.ticket,
            self.receptionist_findings,
            self.debugger_findings,
        )

        self.assertTrue(
            any(
                "version of Chrome" in question
                for question in result["follow_up_questions"]
            )
        )

    def test_preserves_the_reported_record_threshold(self):
        result = draft_support_response(
            self.ticket,
            self.receptionist_findings,
            self.debugger_findings,
        )

        self.assertTrue(
            any(
                "500 records" in question
                for question in result["follow_up_questions"]
            )
        )

    def test_does_not_request_information_already_provided(self):
        result = draft_support_response(
            self.ticket,
            self.receptionist_findings,
            self.debugger_findings,
        )

        questions = " ".join(
            result["follow_up_questions"]
        ).lower()

        self.assertNotIn(
            "which operating system",
            questions,
        )

        self.assertNotIn(
            "steps you took",
            questions,
        )

    def test_does_not_include_reporter_email_in_draft(self):
        result = draft_support_response(
            self.ticket,
            self.receptionist_findings,
            self.debugger_findings,
        )

        self.assertNotIn(
            self.ticket.reporter_email,
            result["draft_response"],
        )

    def test_records_retrieved_evidence_for_review(self):
        self.debugger_findings["investigation_status"] = (
            "evidence_found"
        )

        self.debugger_findings["documented_evidence"] = [
            {
                "document_id": "doc-123",
                "document_title": "Report Generation Guide",
                "chunk_id": "chunk-456",
                "chunk_index": 2,
                "matched_terms": ["report", "records"],
                "matched_phrases": ["generate report"],
                "content": "Internal technical documentation.",
            }
        ]

        result = draft_support_response(
            self.ticket,
            self.receptionist_findings,
            self.debugger_findings,
        )

        self.assertEqual(
            len(result["evidence_references"]),
            1,
        )

        self.assertIn(
            "not yet confirmed",
            result["draft_response"],
        )

    def test_rejects_invalid_findings(self):
        with self.assertRaises(TypeError):
            draft_support_response(
                self.ticket,
                None,
                self.debugger_findings,
            )

    def test_records_support_rep_version(self):
        result = draft_support_response(
            self.ticket,
            self.receptionist_findings,
            self.debugger_findings,
        )

        self.assertEqual(
            result["responder"]["version"],
            "1.0.0",
        )