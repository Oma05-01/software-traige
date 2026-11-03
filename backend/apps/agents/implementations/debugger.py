
import re

from apps.knowledge.services import search_knowledge, search_knowledge_batch


STOP_WORDS = {
    "a",
    "an",
    "the",
    "and",
    "or",
    "but",
    "if",
    "in",
    "on",
    "at",
    "by",
    "as",
    "to",
    "of",
    "for",
    "with",
    "from",
    "that",
    "this",
    "when",
    "whenever",
    "where",
    "what",
    "which",
    "while",
    "into",
    "than",
    "then",
    "them",
    "they",
    "their",
    "there",
    "have",
    "has",
    "had",
    "does",
    "doing",
    "done",
    "been",
    "being",
    "were",
    "was",
    "will",
    "would",
    "could",
    "should",
    "can",
    "not",
    "are",
    "is",
    "be",
    "it",
    "i",
    "we",
    "he",
    "she",
    "my",
    "our",
    "your",
    "you",
    "all",
    "any",
    "some",
    "more",
    "less",
    "large",
    "larger",
    "small",
    "smaller",
    "application",
    "system",
    "please",
    "issue",
    "problem",
    "reported",
    "expected",
    "actual",
    "user",
    "users",
    "whenever",
    "becomes",
    "containing",
    "open",
    "select",
    "click",
}


# Search fields in descending diagnostic importance.
SEARCH_FIELD_PRIORITY = (
    "actual_behavior",
    "description",
    "steps_to_reproduce",
    "title",
    "expected_behavior",
)


TOKEN_PATTERN = re.compile(
    r"[a-z][a-z0-9_+#.-]*|\d+[a-z][a-z0-9_+#.-]*|\d+(?:\.\d+)?",
    re.IGNORECASE,
)


def tokenize(text):
    """
    Extract searchable words, technical identifiers and numbers.

    Examples:
        HTTP 500 -> ["http", "500"]
        Node.js -> ["node.js"]
        2FA -> ["2fa"]
        C++ -> ["c++"]
    """

    return [
        match.group(0).lower().strip("._-")
        for match in TOKEN_PATTERN.finditer(text or "")
        if match.group(0).strip("._-")
    ]


def is_searchable_term(word):
    """Determine whether an extracted token is useful for retrieval."""

    if word in STOP_WORDS:
        return False

    # Preserve technical language and numerical conditions.
    if word in {"c++", "c#"}:
        return True

    if word.isdigit():
        return len(word) >= 2

    return len(word) >= 3


def get_ticket_field_texts(ticket):
    """
    Return ticket text in diagnostic priority order.
    """

    return [
        getattr(ticket, field, "") or ""
        for field in SEARCH_FIELD_PRIORITY
    ]


def extract_search_terms(ticket, max_terms=12):
    """
    Extract individual search terms using field-aware prioritisation.

    Actual behaviour and reproduction details take priority over
    generic words appearing in the ticket title.
    """

    if not isinstance(max_terms, int) or isinstance(max_terms, bool):
        raise TypeError("max_terms must be an integer.")

    if max_terms < 0:
        raise ValueError("max_terms cannot be negative.")
    if max_terms == 0:
        return []

    terms = []
    seen = set()

    for field_text in get_ticket_field_texts(ticket):

        for word in tokenize(field_text):

            if not is_searchable_term(word):
                continue

            if word in seen:
                continue

            seen.add(word)
            terms.append(word)

            if len(terms) >= max_terms:
                return terms

    return terms


def extract_search_phrases(ticket, max_phrases=6):
    """
    Extract useful adjacent word combinations.

    Examples:
        "dashboard freezes"
        "generate a report"
        "500 records"

    Phrases are searched separately from individual words because
    combinations can provide more specific retrieval signals.
    """

    if not isinstance(max_phrases, int) or isinstance(max_phrases, bool):
        raise TypeError("max_phrases must be an integer.")

    if max_phrases < 0:
        raise ValueError("max_phrases cannot be negative.")
    if max_phrases == 0:
        return []

    phrases = []
    seen = set()

    for field_text in get_ticket_field_texts(ticket):

        words = tokenize(field_text)

        for phrase_size in (2, 3):

            for start in range(len(words) - phrase_size + 1):

                window = words[start:start + phrase_size]

                # At least two meaningful terms must be present.
                meaningful = [
                    word
                    for word in window
                    if is_searchable_term(word)
                ]

                if len(meaningful) < 2:
                    continue

                # Avoid phrases beginning or ending with stop words.
                if (
                    not is_searchable_term(window[0])
                    or not is_searchable_term(window[-1])
                ):
                    continue

                # Allow at most one connecting stop word inside
                # a phrase, e.g. "generate a report".
                internal_stop_words = sum(
                    1
                    for word in window[1:-1]
                    if not is_searchable_term(word)
                )

                if internal_stop_words > 1:
                    continue

                phrase = " ".join(window)

                if phrase in seen:
                    continue

                seen.add(phrase)
                phrases.append(phrase)

                if len(phrases) >= max_phrases:
                    return phrases

    return phrases

def assess_retrieval_relevance(candidate, total_search_terms):
    """
    Assess how strongly a retrieved chunk matches the ticket
    through its actual content.

    This evaluates retrieval relevance, not whether the
    document proves a technical root cause.
    """

    content_terms = candidate["matched_terms_in_content"]
    content_phrases = candidate["matched_phrases_in_content"]

    term_count = len(content_terms)
    phrase_count = len(content_phrases)

    term_coverage = (
        term_count / total_search_terms
        if total_search_terms
        else 0.0
    )

    if phrase_count >= 2 and term_count >= 3:
        level = "strong"

    elif (
        phrase_count >= 1
        or (
            term_count >= 3
            and term_coverage >= 0.25
        )
    ):
        level = "moderate"

    else:
        level = "weak"

    return {
        "level": level,
        "content_term_matches": term_count,
        "content_phrase_matches": phrase_count,
        "title_term_matches": len(
            candidate["matched_terms_in_title"]
        ),
        "title_phrase_matches": len(
            candidate["matched_phrases_in_title"]
        ),
        "term_coverage": round(term_coverage, 4),
    }

def retrieve_evidence(ticket, max_results=5):
    """
    Retrieve documentation using batched term and phrase searches.

    Retrieved candidates are assessed using content-level matches.

    Only moderate and strong retrieval matches are promoted to
    documented_evidence.
    """

    if not isinstance(max_results, int) or isinstance(max_results, bool):
        raise TypeError("max_results must be an integer.")

    if not 1 <= max_results <= 20:
        raise ValueError(
            "max_results must be between 1 and 20."
        )

    search_terms = extract_search_terms(ticket)
    search_phrases = extract_search_phrases(ticket)

    queries = (
        [(term, "term") for term in search_terms]
        + [(phrase, "phrase") for phrase in search_phrases]
    )

    if queries:
        candidates = search_knowledge_batch(
            queries,
            limit=min(100, max(20, max_results * 10)),
        )
    else:
        candidates = []

    ranked = []

    for candidate in candidates:

        content_terms = candidate[
            "matched_terms_in_content"
        ]

        content_phrases = candidate[
            "matched_phrases_in_content"
        ]

        title_terms = candidate[
            "matched_terms_in_title"
        ]

        title_phrases = candidate[
            "matched_phrases_in_title"
        ]

        match_score = (
            len(content_terms)
            + (2 * len(content_phrases))
        )

        relevance = assess_retrieval_relevance(
            candidate,
            len(search_terms),
        )

        ranked.append({
            **candidate,
            "match_score": match_score,
            "retrieval_relevance": relevance,
        })

    ranked.sort(
        key=lambda item: (
            -item["match_score"],
            -len(item["matched_phrases_in_content"]),
            -len(item["matched_terms_in_content"]),
            -item["search_rank"],
            item["chunk"].document.title,
            item["chunk"].chunk_index,
        )
    )

    retrieved_candidates = []

    for item in ranked[:max_results]:

        chunk = item["chunk"]
        document = chunk.document

        retrieved_candidates.append({
            "chunk_id": str(chunk.id),
            "document_id": str(document.id),
            "document_title": document.title,
            "source_type": document.source_type,
            "source_reference": document.source_reference,
            "chunk_index": chunk.chunk_index,
            "content": chunk.content,

            "matched_terms": sorted(
                item["matched_terms"]
            ),
            "matched_phrases": sorted(
                item["matched_phrases"]
            ),

            "matched_terms_in_content": sorted(
                item["matched_terms_in_content"]
            ),
            "matched_phrases_in_content": sorted(
                item["matched_phrases_in_content"]
            ),
            "matched_terms_in_title": sorted(
                item["matched_terms_in_title"]
            ),
            "matched_phrases_in_title": sorted(
                item["matched_phrases_in_title"]
            ),

            "match_score": item["match_score"],
            "search_rank": round(
                item["search_rank"],
                6,
            ),
            "retrieval_relevance": item[
                "retrieval_relevance"
            ],
        })

    evidence = [
        candidate
        for candidate in retrieved_candidates
        if candidate["retrieval_relevance"]["level"]
        in {"moderate", "strong"}
    ]

    return {
        "search_terms": search_terms,
        "search_phrases": search_phrases,
        "evidence": evidence,
        "retrieved_candidates": retrieved_candidates,
    }

def investigate_ticket(ticket, max_results=5, receptionist_findings=None):
    """
    Performs deterministic, knowledge-based investigation.

    Retrieval relevance is assessed separately from technical
    evidence and root-cause verification.
    """

    retrieval = retrieve_evidence(
        ticket,
        max_results=max_results,
    )

    evidence = retrieval["evidence"]
    candidates = retrieval["retrieved_candidates"]

    if evidence:

        investigation_status = "evidence_found"

        summary = (
            f"Retrieved {len(evidence)} documentation "
            "sections with sufficient content-level relevance."
        )

    else:

        investigation_status = "no_relevant_evidence"

        if candidates:
            summary = (
                f"Retrieved {len(candidates)} candidate "
                "documentation sections, but none met the "
                "minimum content-relevance threshold."
            )
        else:
            summary = (
                "No technical documentation candidates "
                "were retrieved."
            )

    if evidence:
        unresolved_questions = []

    elif candidates:
        unresolved_questions = [
            (
                "The retrieved documentation did not contain "
                "sufficient matching technical details."
            ),
            (
                "Additional documentation describing the "
                "reported behaviour is needed."
            ),
        ]

    else:
        unresolved_questions = [
            "Additional technical documentation is needed."
        ]

    return {
        "investigation_status": investigation_status,

        "issue_summary": ticket.title,

        "summary": summary,

        "documented_evidence": evidence,

        "retrieved_candidates": candidates,

        "root_cause": {
            "status": "not_established",
            "explanation": (
                "The deterministic retrieval engine "
                "does not independently establish root causes."
            ),
        },

        "possible_explanations": [],

        "recommended_workaround": None,

        "unresolved_questions": unresolved_questions,

        "retrieval_metadata": {
            "method": "postgres_full_text_search_batched",
            "search_terms": retrieval["search_terms"],
            "search_phrases": retrieval["search_phrases"],
            "evidence_count": len(evidence),
            "candidate_count": len(candidates),
        },

        "investigator": {
            "name": "deterministic_debugger",
            "version": "1.2.0",
        },
    }