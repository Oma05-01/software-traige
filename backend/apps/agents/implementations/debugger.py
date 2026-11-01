
import re

from apps.knowledge.services import search_knowledge


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


def retrieve_evidence(ticket, max_results=5):
    """
    Retrieve supporting knowledge using individual terms and phrases.

    Evidence is ranked using:
        1. Number of matched phrases.
        2. Number of matched individual terms.
        3. PostgreSQL search relevance.

    Phrase matches receive additional weight because they generally
    provide a more specific retrieval signal.
    """

    if not isinstance(max_results, int) or isinstance(max_results, bool):
        raise TypeError("max_results must be an integer.")

    if not 1 <= max_results <= 20:
        raise ValueError(
            "max_results must be between 1 and 20."
        )

    search_terms = extract_search_terms(ticket)
    search_phrases = extract_search_phrases(ticket)

    retrieved = {}

    def collect_results(query, query_type):
        chunks = search_knowledge(
            query,
            limit=5,
        )

        for chunk in chunks:

            chunk_id = str(chunk.id)

            if chunk_id not in retrieved:
                retrieved[chunk_id] = {
                    "chunk": chunk,
                    "matched_terms": set(),
                    "matched_phrases": set(),
                    "search_rank": 0.0,
                }

            entry = retrieved[chunk_id]

            if query_type == "term":
                entry["matched_terms"].add(query)

            elif query_type == "phrase":
                entry["matched_phrases"].add(query)

            entry["search_rank"] = max(
                entry["search_rank"],
                float(chunk.rank),
            )

    # Search individual terms.
    for term in search_terms:
        collect_results(term, "term")

    # Search quoted phrases using PostgreSQL web-search syntax.
    for phrase in search_phrases:
        collect_results(
            f'"{phrase}"',
            "phrase",
        )

    # Calculate a score for each retrieved chunk.
    for entry in retrieved.values():

        term_count = len(entry["matched_terms"])
        phrase_count = len(entry["matched_phrases"])

        entry["match_score"] = (
            term_count + (2 * phrase_count)
        )

    ranked = sorted(
        retrieved.values(),
        key=lambda item: (
            -item["match_score"],
            -len(item["matched_phrases"]),
            -len(item["matched_terms"]),
            -item["search_rank"],
            item["chunk"].document.title,
            item["chunk"].chunk_index,
        ),
    )

    evidence = []

    for item in ranked[:max_results]:

        chunk = item["chunk"]
        document = chunk.document

        evidence.append({
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
            "match_score": item["match_score"],
            "search_rank": round(
                item["search_rank"],
                6,
            ),
        })

    return {
        "search_terms": search_terms,
        "search_phrases": search_phrases,
        "evidence": evidence,
    }


def investigate_ticket(ticket, max_results=5):
    """
    Performs deterministic, knowledge-based investigation.

    Retrieval provides supporting documentation. It does not
    independently establish a root cause or recommend a fix.
    """

    retrieval = retrieve_evidence(
        ticket,
        max_results=max_results,
    )

    evidence = retrieval["evidence"]

    if evidence:

        investigation_status = "evidence_found"

        summary = (
            f"Retrieved {len(evidence)} relevant "
            "technical documentation sections."
        )

    else:

        investigation_status = "no_relevant_evidence"

        summary = (
            "No sufficiently relevant technical "
            "documentation was retrieved."
        )

    return {
        "investigation_status": investigation_status,

        "issue_summary": ticket.title,

        "summary": summary,

        "documented_evidence": evidence,

        "root_cause": {
            "status": "not_established",
            "explanation": (
                "The deterministic retrieval engine "
                "does not independently establish root causes."
            ),
        },

        "possible_explanations": [],

        "recommended_workaround": None,

        "unresolved_questions": (
            [
                "Additional technical documentation is needed."
            ]
            if not evidence
            else []
        ),

        "retrieval_metadata": {
            "method": "postgres_full_text_search",
            "search_terms": retrieval["search_terms"],
            "search_phrases": retrieval["search_phrases"],
            "evidence_count": len(evidence),
        },

        "investigator": {
            "name": "deterministic_debugger",
            "version": "1.1.0",
        },
    }
