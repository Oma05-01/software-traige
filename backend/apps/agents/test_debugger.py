from django.test import TestCase

from apps.tickets.models import Ticket
from apps.knowledge.services import ingest_document

from apps.agents.implementations.debugger import (
    extract_search_terms,
    retrieve_evidence,
    investigate_ticket,
)


class DebuggerInvestigationTests(TestCase):

    def setUp(self):

        self.document = ingest_document(
            title="PDF Upload Troubleshooting Guide",
            content=(
                "The PDF upload endpoint rejects files "
                "larger than 25 MB. "
                "The upload service validates file sizes "
                "before processing. "
                "Requests may fail when the processing "
                "service encounters a timeout. "
                "The configured upload limit is 25 MB."
            ),
        )

        self.ticket = Ticket.objects.create(
            title="PDF upload failure",
            description=(
                "Uploading PDF files larger than 25 MB "
                "causes an error."
            ),
            reporter_email="reporter@example.com",
            environment="Windows 11, Chrome",
        )

    def test_extracts_technical_search_terms(self):

        terms = extract_search_terms(self.ticket)

        self.assertIn("pdf", terms)
        self.assertIn("upload", terms)

        self.assertNotIn("the", terms)
        self.assertNotIn("application", terms)

    def test_retrieves_relevant_documentation(self):

        result = investigate_ticket(self.ticket)

        self.assertEqual(
            result["investigation_status"],
            "evidence_found",
        )

        self.assertGreater(
            len(result["documented_evidence"]),
            0,
        )

        self.assertEqual(
            result["documented_evidence"][0]["document_id"],
            str(self.document.id),
        )

    def test_evidence_contains_source_information(self):

        result = investigate_ticket(self.ticket)

        evidence = result["documented_evidence"][0]

        self.assertIn("document_id", evidence)
        self.assertIn("document_title", evidence)
        self.assertIn("chunk_id", evidence)
        self.assertIn("content", evidence)
        self.assertIn("matched_terms", evidence)

    def test_debugger_does_not_invent_root_cause(self):

        result = investigate_ticket(self.ticket)

        self.assertEqual(
            result["root_cause"]["status"],
            "not_established",
        )

        self.assertIsNone(
            result["recommended_workaround"]
        )

        self.assertEqual(
            result["possible_explanations"],
            [],
        )

    def test_no_relevant_documentation_is_reported(self):

        unrelated_ticket = Ticket.objects.create(
            title="Calendar integration issue",
            description=(
                "The calendar synchronization "
                "does not update events."
            ),
            reporter_email="another@example.com",
        )

        result = investigate_ticket(unrelated_ticket)

        self.assertEqual(
            result["investigation_status"],
            "no_relevant_evidence",
        )

        self.assertEqual(
            result["documented_evidence"],
            [],
        )

        self.assertEqual(
            result["retrieval_metadata"]["evidence_count"],
            0,
        )

    def test_retrieval_respects_max_results(self):

        for index in range(7):
            ingest_document(
                title=f"PDF Technical Reference {index}",
                content=(
                    f"PDF upload processing reference {index}. "
                    "The upload service validates PDF files."
                ),
            )

        result = retrieve_evidence(
            self.ticket,
            max_results=3,
        )

        self.assertLessEqual(
            len(result["evidence"]),
            3,
        )

    def test_invalid_result_limit_is_rejected(self):

        with self.assertRaises(ValueError):
            retrieve_evidence(
                self.ticket,
                max_results=0,
            )

    def test_inactive_documentation_is_not_used(self):

        self.document.is_active = False
        self.document.save(
            update_fields=["is_active"]
        )

        result = investigate_ticket(self.ticket)

        self.assertEqual(
            result["investigation_status"],
            "no_relevant_evidence",
        )

    def test_investigator_version_is_recorded(self):

        result = investigate_ticket(self.ticket)

        self.assertEqual(
            result["investigator"]["name"],
            "deterministic_debugger",
        )

        self.assertEqual(
            result["investigator"]["version"],
            "1.1.0",
        )