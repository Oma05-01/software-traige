from django.db import transaction

from django.contrib.postgres.search import (
    SearchQuery,
    SearchRank,
    SearchVector,
)

from .models import (
    KnowledgeDocument,
    KnowledgeChunk,
)


def split_into_chunks(
    content,
    max_words=180,
    overlap_words=30,
):
    """
    Splits document content into overlapping word chunks.
    """

    if max_words < 1:
        raise ValueError("max_words must be positive.")

    if not 0 <= overlap_words < max_words:
        raise ValueError(
            "overlap_words must be between zero "
            "and max_words - 1."
        )

    words = content.split()

    if not words:
        return []

    step = max_words - overlap_words

    chunks = []

    for start in range(0, len(words), step):

        chunk_words = words[
            start:start + max_words
        ]

        if not chunk_words:
            break

        chunks.append(" ".join(chunk_words))

        if start + max_words >= len(words):
            break

    return chunks


@transaction.atomic
def ingest_document(
    title,
    content,
    source_type=KnowledgeDocument.SourceType.MANUAL,
    source_reference="",
):
    """
    Creates a knowledge document and its searchable chunks.
    """

    if not title or not title.strip():
        raise ValueError("Document title cannot be empty.")

    if not content or not content.strip():
        raise ValueError("Document content cannot be empty.")

    if source_type not in KnowledgeDocument.SourceType.values:
        raise ValueError("Invalid document source type.")

    chunks = split_into_chunks(content)

    document = KnowledgeDocument.objects.create(
        title=title.strip(),
        content=content.strip(),
        source_type=source_type,
        source_reference=source_reference,
    )

    KnowledgeChunk.objects.bulk_create([
        KnowledgeChunk(
            document=document,
            chunk_index=index,
            content=chunk,
        )
        for index, chunk in enumerate(chunks)
    ])

    return document


def search_knowledge(query, limit=5):
    """
    Searches active knowledge documents using PostgreSQL
    full-text search, returning the most relevant chunks.
    """

    if not isinstance(query, str):
        raise TypeError("Search query must be a string.")

    if not isinstance(limit, int) or isinstance(limit, bool):
        raise TypeError("Search limit must be an integer.")

    if not 1 <= limit <= 20:
        raise ValueError("Search limit must be between 1 and 20.")

    query = query.strip()

    if not query:
        return KnowledgeChunk.objects.none()

    search_vector = SearchVector(
        "content",
        config="english",
    )

    search_query = SearchQuery(
        query,
        config="english",
        search_type="websearch",
    )

    return (
        KnowledgeChunk.objects
        .filter(document__is_active=True)
        .annotate(
            search_vector=search_vector,
            rank=SearchRank(
                search_vector,
                search_query,
            ),
        )
        .filter(search_vector=search_query)
        .select_related("document")
        .order_by("-rank", "document__title", "chunk_index")
    )[:limit]