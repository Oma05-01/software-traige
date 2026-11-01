from django.test import TestCase

from .models import KnowledgeDocument, KnowledgeChunk
from .services import (
    split_into_chunks,
    ingest_document,
    search_knowledge,
)


class KnowledgeIngestionTests(TestCase):

    def test_document_creates_searchable_chunks(self):

        content = (
            "PDF uploads are limited to 25 MB. "
            "The upload service validates file sizes "
            "before processing. "
        ) * 30

        document = ingest_document(
            title="PDF Upload Documentation",
            content=content,
        )

        self.assertEqual(
            document.chunks.count(),
            len(split_into_chunks(content)),
        )

        self.assertGreater(
            document.chunks.count(),
            1,
        )

        self.assertEqual(
            document.source_type,
            KnowledgeDocument.SourceType.MANUAL,
        )

    def test_empty_document_content_is_rejected(self):

        with self.assertRaises(ValueError):
            ingest_document(
                title="Empty document",
                content="   ",
            )

        self.assertEqual(
            KnowledgeDocument.objects.count(),
            0,
        )

    def test_empty_document_title_is_rejected(self):

        with self.assertRaises(ValueError):
            ingest_document(
                title=" ",
                content="Some technical documentation.",
            )

    def test_invalid_chunk_configuration_is_rejected(self):

        with self.assertRaises(ValueError):
            split_into_chunks(
                "Some content",
                max_words=10,
                overlap_words=10,
            )

    def test_chunk_overlap_is_preserved(self):

        words = [f"word{i}" for i in range(400)]

        content = " ".join(words)

        chunks = split_into_chunks(
            content,
            max_words=180,
            overlap_words=30,
        )

        first_chunk = chunks[0].split()
        second_chunk = chunks[1].split()

        self.assertEqual(
            first_chunk[-30:],
            second_chunk[:30],
        )


class KnowledgeRetrievalTests(TestCase):

    def setUp(self):

        self.document = ingest_document(
            title="PDF Upload Troubleshooting",
            content=(
                "The PDF upload endpoint rejects files "
                "larger than 25 MB. "
                "Upload requests can also fail when "
                "the processing service encounters a timeout. "
                "The application should return a clear "
                "validation error when the file exceeds "
                "the configured upload limit."
            ),
        )

        self.unrelated_document = ingest_document(
            title="Dashboard Styling Guide",
            content=(
                "The dashboard uses responsive layouts, "
                "typography and spacing rules. "
                "Navigation elements should remain "
                "consistent across screen sizes."
            ),
        )

    def test_retrieves_relevant_document_chunks(self):

        results = search_knowledge(
            "PDF upload 25 MB",
        )

        results = list(results)

        self.assertGreater(len(results), 0)

        self.assertEqual(
            results[0].document,
            self.document,
        )

    def test_unrelated_documents_are_not_returned(self):

        results = list(
            search_knowledge(
                "PDF upload timeout",
            )
        )

        document_ids = {
            result.document_id
            for result in results
        }

        self.assertIn(
            self.document.id,
            document_ids,
        )

        self.assertNotIn(
            self.unrelated_document.id,
            document_ids,
        )

    def test_inactive_documents_are_excluded(self):

        self.document.is_active = False

        self.document.save(
            update_fields=["is_active"]
        )

        results = list(
            search_knowledge(
                "PDF upload 25 MB",
            )
        )

        self.assertEqual(len(results), 0)

    def test_empty_search_returns_no_results(self):

        results = search_knowledge("   ")

        self.assertEqual(len(results), 0)

    def test_invalid_search_limit_is_rejected(self):

        with self.assertRaises(ValueError):
            search_knowledge(
                "PDF upload",
                limit=0,
            )

    def test_search_results_have_relevance_ranking(self):

        results = list(
            search_knowledge(
                "PDF upload 25 MB",
            )
        )

        self.assertGreater(len(results), 0)

        self.assertTrue(
            hasattr(results[0], "rank")
        )