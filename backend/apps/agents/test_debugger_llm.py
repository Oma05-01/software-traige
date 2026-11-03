import json
from unittest.mock import Mock, patch

from django.test import TestCase

from apps.tickets.models import Ticket
from apps.knowledge.services import ingest_document

from apps.agents.implementations.debugger import retrieve_evidence
from apps.agents.implementations.debugger_llm import (
    investigate_ticket_llm,
)


class DebuggerLLMTests(TestCase):

    def setUp(self):
        ingest_document(
            title="PDF Upload Troubleshooting Guide",
            content=(
                "The PDF upload endpoint rejects files "
                "larger than 25 MB. The upload service "
                "validates file sizes before processing. "
                "Requests may fail when the processing "
                "service encounters a timeout."
            ),
        )

        self.ticket = Ticket.objects.create(
            title="PDF upload failure",
            description=(
                "Uploading PDF files larger than 25 MB "
                "causes an error."
            ),
            reporter_name="Private Test Reporter",
            reporter_email="private@example.com",
            environment="Windows 11, Chrome",
        )

        self.receptionist_findings = {
            "category": "bug",
            "priority": "high",
            "classification_confidence": "high",
        }

        self.provider = Mock()
        self.provider.provider_name = "groq"
        self.provider.model_name = "openai/gpt-oss-20b"

    def get_valid_evidence(self):
        evidence = retrieve_evidence(
            self.ticket
        )["evidence"]

        self.assertGreater(len(evidence), 0)

        return evidence

    def build_generated_response(self, chunk_id):
        return {
            "investigation_summary": (
                "The documentation describes an upload-size "
                "validation rule. The relationship to this "
                "specific incident has not been independently verified."
            ),
            "possible_explanations_json": json.dumps([
                {
                    "explanation": (
                        "The documented upload-size validation "
                        "may be related to the reported failure."
                    ),
                    "confidence": "medium",
                    "evidence_ids": [chunk_id],
                }
            ]),
            "recommended_workaround_json": "{}",
            "unresolved_questions_json": json.dumps([
                "What exact error message appears during upload?",
                "Does the failure occur with files smaller than 25 MB?",
            ]),
        }

    @patch(
        "apps.agents.implementations.debugger_llm.get_llm_provider"
    )
    def test_investigation_returns_validated_findings(
        self,
        mock_get_provider,
    ):
        evidence = self.get_valid_evidence()
        chunk_id = evidence[0]["chunk_id"]

        self.provider.generate_structured.return_value = (
            self.build_generated_response(chunk_id)
        )

        mock_get_provider.return_value = self.provider

        result = investigate_ticket_llm(
            self.ticket,
            receptionist_findings=self.receptionist_findings,
        )

        self.assertEqual(
            result["investigation_status"],
            "evidence_found",
        )

        self.assertEqual(
            result["root_cause"]["status"],
            "not_established",
        )

        self.assertEqual(
            len(result["possible_explanations"]),
            1,
        )

        explanation = result["possible_explanations"][0]

        self.assertEqual(
            explanation["evidence_references"][0]["chunk_id"],
            chunk_id,
        )

        self.assertEqual(
            result["investigator"]["name"],
            "groq_debugger",
        )

    @patch(
        "apps.agents.implementations.debugger_llm.get_llm_provider"
    )
    def test_unknown_evidence_references_are_rejected(
        self,
        mock_get_provider,
    ):
        self.get_valid_evidence()

        self.provider.generate_structured.return_value = (
            self.build_generated_response(
                "not-a-real-evidence-id"
            )
        )

        mock_get_provider.return_value = self.provider

        result = investigate_ticket_llm(
            self.ticket,
            receptionist_findings=self.receptionist_findings,
        )

        self.assertEqual(
            result["possible_explanations"],
            [],
        )

    @patch(
        "apps.agents.implementations.debugger_llm.get_llm_provider"
    )
    def test_reporter_identity_is_excluded_from_llm_input(
        self,
        mock_get_provider,
    ):
        evidence = self.get_valid_evidence()

        self.provider.generate_structured.return_value = (
            self.build_generated_response(
                evidence[0]["chunk_id"]
            )
        )

        mock_get_provider.return_value = self.provider

        investigate_ticket_llm(
            self.ticket,
            receptionist_findings=self.receptionist_findings,
        )

        call_kwargs = (
            self.provider.generate_structured.call_args.kwargs
        )

        serialized_input = call_kwargs["messages"][1]["content"]

        self.assertNotIn(
            "private@example.com",
            serialized_input,
        )

        self.assertNotIn(
            "Private Test Reporter",
            serialized_input,
        )

        self.assertNotIn(
            str(self.ticket.id),
            serialized_input,
        )

    @patch(
        "apps.agents.implementations.debugger_llm.get_llm_provider"
    )
    def test_no_evidence_prevents_unsupported_explanations(
        self,
        mock_get_provider,
    ):
        unrelated_ticket = Ticket.objects.create(
            title="Calendar synchronization problem",
            description=(
                "Calendar events are not synchronizing."
            ),
            reporter_email="another@example.com",
        )

        self.provider.generate_structured.return_value = (
            self.build_generated_response(
                "invented-evidence-id"
            )
        )

        mock_get_provider.return_value = self.provider

        result = investigate_ticket_llm(
            unrelated_ticket,
            receptionist_findings={
                "category": "bug",
                "priority": "medium",
            },
        )

        self.assertEqual(
            result["investigation_status"],
            "no_relevant_evidence",
        )

        self.assertEqual(
            result["documented_evidence"],
            [],
        )

        self.assertEqual(
            result["possible_explanations"],
            [],
        )

        self.assertIsNone(
            result["recommended_workaround"],
        )

        self.assertEqual(
            result["root_cause"]["status"],
            "not_established",
        )