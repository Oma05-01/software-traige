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
            "1.2.0",
        )


    def test_title_only_match_is_retrieved_but_not_promoted(self):
        title_only_document = ingest_document(
            title="PostgreSQL Connection Pooling Troubleshooting",
            content=(
                "This reference discusses resource allocation "
                "and lifecycle management."
            ),
        )

        ticket = Ticket.objects.create(
            title="PostgreSQL connection pool failure",
            description=(
                "The application cannot establish "
                "a reusable database session."
            ),
            reporter_email="another@example.com",
        )

        result = investigate_ticket(ticket)

        candidate = next(
            (
                item
                for item in result["retrieved_candidates"]
                if item["document_id"] == str(title_only_document.id)
            ),
            None,
        )

        self.assertIsNotNone(candidate)

        self.assertEqual(
            candidate["retrieval_relevance"]["level"],
            "weak",
        )

        evidence_document_ids = {
            item["document_id"]
            for item in result["documented_evidence"]
        }

        self.assertNotIn(
            str(title_only_document.id),
            evidence_document_ids,
        )
    
    def test_retrieval_uses_one_database_query(self):

        with self.assertNumQueries(1):
            result = retrieve_evidence(self.ticket)

        self.assertGreater(
            len(result["evidence"]),
            0,
        )

    def test_batched_retrieval_preserves_matched_terms(self):

        result = retrieve_evidence(self.ticket)

        matched_terms = {
            term
            for item in result["evidence"]
            for term in item["matched_terms"]
        }

        self.assertIn("pdf", matched_terms)
        self.assertIn("upload", matched_terms)

    def test_zero_search_term_limit_returns_empty_list(self):

        self.assertEqual(
            extract_search_terms(
                self.ticket,
                max_terms=0,
            ),
            [],
        )

    def test_zero_search_phrase_limit_returns_empty_list(self):

        from apps.agents.implementations.debugger import (
            extract_search_phrases,
        )

        self.assertEqual(
            extract_search_phrases(
                self.ticket,
                max_phrases=0,
            ),
            [],
        )

    def test_title_only_match_is_not_promoted_to_evidence(self):

        title_only_document = ingest_document(
            title="PostgreSQL Connection Pooling Troubleshooting",
            content=(
                "This reference discusses resource allocation "
                "and lifecycle management."
            ),
        )

        ticket = Ticket.objects.create(
            title="PostgreSQL connection pool failure",
            description=(
                "The application cannot establish "
                "a reusable database session."
            ),
            reporter_email="another@example.com",
        )

        result = investigate_ticket(ticket)

        candidate = next(
            (
                item
                for item in result["retrieved_candidates"]
                if item["document_id"] == str(title_only_document.id)
            ),
            None,
        )

        self.assertIsNotNone(candidate)

        self.assertEqual(
            candidate["retrieval_relevance"]["level"],
            "weak",
        )

        self.assertNotIn(
            str(title_only_document.id),
            {
                item["document_id"]
                for item in result["documented_evidence"]
            },
        )

        self.assertEqual(
            result["investigation_status"],
            "no_relevant_evidence",
        )

    def test_relevant_documentation_is_promoted_to_evidence(self):

        result = investigate_ticket(self.ticket)

        self.assertGreater(
            len(result["documented_evidence"]),
            0,
        )

        for item in result["documented_evidence"]:
            self.assertIn(
                item["retrieval_relevance"]["level"],
                {"moderate", "strong"},
            )