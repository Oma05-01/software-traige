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

from django.db.models import (
    BooleanField,
    Case,
    ExpressionWrapper,
    FloatField,
    Q,
    Value,
    When,
    F,
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
    Search active knowledge documents using PostgreSQL
    full-text search.

    Both chunk content and document titles are searchable.

    Document-title matches receive additional ranking weight.
    """

    if not isinstance(query, str):
        raise TypeError("Search query must be a string.")

    if not isinstance(limit, int) or isinstance(limit, bool):
        raise TypeError("Search limit must be an integer.")

    if not 1 <= limit <= 20:
        raise ValueError(
            "Search limit must be between 1 and 20."
        )

    query = query.strip()

    if not query:
        return KnowledgeChunk.objects.none()

    search_query = SearchQuery(
        query,
        config="english",
        search_type="websearch",
    )

    content_vector = SearchVector(
        "content",
        config="english",
    )

    title_vector = SearchVector(
        "document__title",
        config="english",
    )

    return (
        KnowledgeChunk.objects
        .filter(document__is_active=True)
        .annotate(
            content_vector=content_vector,
            title_vector=title_vector,
            content_rank=SearchRank(
                content_vector,
                search_query,
            ),
            title_rank=SearchRank(
                title_vector,
                search_query,
            ),
        )
        .filter(
            Q(content_vector=search_query)
            | Q(title_vector=search_query)
        )
        .annotate(
            rank=ExpressionWrapper(
                F("content_rank")
                + Value(2.0) * F("title_rank"),
                output_field=FloatField(),
            )
        )
        .select_related("document")
        .order_by(
            "-rank",
            "document__title",
            "chunk_index",
        )
    )[:limit]

def search_knowledge_batch(queries, limit=50):
    """
    Search multiple terms and phrases in one database query.

    Args:
        queries: List of (query_text, query_type) tuples.
                 query_type is either "term" or "phrase".
        limit: Maximum number of candidate chunks.

    Returns:
        A list of dictionaries containing:
            chunk
            matched_terms
            matched_phrases
            search_rank
            combined_rank
    """

    if not isinstance(queries, (list, tuple)):
        raise TypeError("Queries must be a list or tuple.")

    if not isinstance(limit, int) or isinstance(limit, bool):
        raise TypeError("Search limit must be an integer.")

    if not 1 <= limit <= 100:
        raise ValueError("Search limit must be between 1 and 100.")

    normalized_queries = []
    seen = set()

    for item in queries:

        if not isinstance(item, (list, tuple)) or len(item) != 2:
            raise ValueError(
                "Each query must contain query text and query type."
            )

        query_text, query_type = item

        if not isinstance(query_text, str):
            raise TypeError("Query text must be a string.")

        query_text = query_text.strip()

        if not query_text:
            continue

        if query_type not in {"term", "phrase"}:
            raise ValueError("Invalid query type.")

        key = (query_text, query_type)

        if key in seen:
            continue

        seen.add(key)
        normalized_queries.append(key)

    if not normalized_queries:
        return []

    content_vector = SearchVector(
        "content",
        config="english",
    )

    title_vector = SearchVector(
        "document__title",
        config="english",
    )

    combined_condition = Q()

    annotations = {}

    combined_rank = Value(
        0.0,
        output_field=FloatField(),
    )

    for index, (text, query_type) in enumerate(
        normalized_queries
    ):

        query_string = (
            f'"{text}"'
            if query_type == "phrase"
            else text
        )

        search_query = SearchQuery(
            query_string,
            config="english",
            search_type="websearch",
        )

        content_match_condition = Q(
            content_vector=search_query
        )

        title_match_condition = Q(
            title_vector=search_query
        )

        match_condition = (
            content_match_condition
            | title_match_condition
        )

        combined_condition |= match_condition

        annotations[
            f"batch_content_match_{index}"
        ] = Case(
            When(
                content_match_condition,
                then=Value(True),
            ),
            default=Value(False),
            output_field=BooleanField(),
        )

        annotations[
            f"batch_title_match_{index}"
        ] = Case(
            When(
                title_match_condition,
                then=Value(True),
            ),
            default=Value(False),
            output_field=BooleanField(),
        )

        query_rank = (
            SearchRank(content_vector, search_query)
            + Value(2.0) * SearchRank(title_vector, search_query)
        )

        annotations[f"batch_rank_{index}"] = Case(
            When(
                match_condition,
                then=query_rank,
            ),
            default=Value(0.0),
            output_field=FloatField(),
        )

        phrase_weight = (
            2.0 if query_type == "phrase" else 1.0
        )

        combined_rank += Case(
            When(
                match_condition,
                then=query_rank * Value(phrase_weight),
            ),
            default=Value(0.0),
            output_field=FloatField(),
        )

    annotations["batch_total_rank"] = ExpressionWrapper(
        combined_rank,
        output_field=FloatField(),
    )

    chunks = (
        KnowledgeChunk.objects
        .filter(document__is_active=True)
        .annotate(
            content_vector=content_vector,
            title_vector=title_vector,
        )
        .filter(combined_condition)
        .annotate(**annotations)
        .select_related("document")
        .order_by(
            "-batch_total_rank",
            "document__title",
            "chunk_index",
        )[:limit]
    )

    results = []

    for chunk in chunks:

        matched_terms = set()
        matched_phrases = set()

        matched_terms_in_content = set()
        matched_phrases_in_content = set()

        matched_terms_in_title = set()
        matched_phrases_in_title = set()

        individual_ranks = []

        for index, (text, query_type) in enumerate(
            normalized_queries
        ):

            content_matched = getattr(
                chunk,
                f"batch_content_match_{index}",
            )

            title_matched = getattr(
                chunk,
                f"batch_title_match_{index}",
            )

            if not content_matched and not title_matched:
                continue

            individual_ranks.append(
                float(
                    getattr(chunk, f"batch_rank_{index}")
                )
            )

            if query_type == "term":
                matched_terms.add(text)

                if content_matched:
                    matched_terms_in_content.add(text)

                if title_matched:
                    matched_terms_in_title.add(text)

            else:
                matched_phrases.add(text)

                if content_matched:
                    matched_phrases_in_content.add(text)

                if title_matched:
                    matched_phrases_in_title.add(text)

        results.append({
            "chunk": chunk,
            "matched_terms": matched_terms,
            "matched_phrases": matched_phrases,
            "matched_terms_in_content": matched_terms_in_content,
            "matched_phrases_in_content": matched_phrases_in_content,
            "matched_terms_in_title": matched_terms_in_title,
            "matched_phrases_in_title": matched_phrases_in_title,
            "search_rank": max(individual_ranks, default=0.0),
            "combined_rank": float(chunk.batch_total_rank),
        })

    return results

