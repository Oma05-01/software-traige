import re


SUPPORT_REP_VERSION = "1.0.0"


def _clean_text(value):
    """Return stripped text, or an empty string for missing values."""
    if not isinstance(value, str):
        return ""

    return value.strip()


def _validate_findings(name, findings):
    if not isinstance(findings, dict):
        raise TypeError(f"{name} must be a dictionary.")


def _get_follow_up_questions(ticket):
    """
    Generate a small number of questions based on missing
    or insufficient information in the ticket.
    """

    questions = []

    environment = _clean_text(
        getattr(ticket, "environment", "")
    )

    steps = _clean_text(
        getattr(ticket, "steps_to_reproduce", "")
    )

    actual_behavior = _clean_text(
        getattr(ticket, "actual_behavior", "")
    )

    description = _clean_text(
        getattr(ticket, "description", "")
    )

    combined_text = " ".join([
        _clean_text(getattr(ticket, "title", "")),
        description,
        actual_behavior,
        steps,
    ])

    # Ask for the environment only when it is missing.
    if not environment:
        questions.append(
            "Which operating system, browser, and application "
            "version are you using?"
        )

    else:
        # If a browser is known but its version is missing,
        # ask for that specific detail.
        browser_match = re.search(
            r"\b(Chrome|Firefox|Edge|Safari)\b",
            environment,
            re.IGNORECASE,
        )

        version_present = re.search(
            r"\b(?:version|v)\s*\d+(?:\.\d+)*"
            r"|\b\d+\.\d+(?:\.\d+)*\b",
            environment,
            re.IGNORECASE,
        )

        if browser_match and not version_present:
            browser = browser_match.group(1)

            questions.append(
                f"Which version of {browser} are you using?"
            )

    # Ask for reproduction steps only when they are missing.
    if not steps:
        questions.append(
            "Could you share the steps you took immediately "
            "before the issue occurred?"
        )

    # Ask for a clearer description if both fields are missing.
    if not actual_behavior and not description:
        questions.append(
            "What happened when you encountered the issue? "
            "Please describe the behaviour you observed."
        )

    # Preserve numerical workload conditions from the report.
    threshold_match = re.search(
        r"\b(\d[\d,]*)\s+(records|rows|items)\b",
        combined_text,
        re.IGNORECASE,
    )

    if threshold_match:
        quantity, unit = threshold_match.groups()

        questions.append(
            f"Does the issue occur consistently with about "
            f"{quantity} {unit}, or does it also happen with "
            "smaller amounts?"
        )

    return questions[:3]


def _build_evidence_references(debugger_findings):
    """Keep references to retrieved evidence for human reviewers."""

    evidence = debugger_findings.get(
        "documented_evidence",
        [],
    )

    if not isinstance(evidence, list):
        return []

    references = []

    for item in evidence:

        if not isinstance(item, dict):
            continue

        references.append({
            "document_id": item.get("document_id"),
            "document_title": item.get("document_title"),
            "chunk_id": item.get("chunk_id"),
            "chunk_index": item.get("chunk_index"),
            "matched_terms": item.get("matched_terms", []),
            "matched_phrases": item.get("matched_phrases", []),
        })

    return references


def draft_support_response(
    ticket,
    receptionist_findings,
    debugger_findings,
):
    """
    Prepare a deterministic support response for human review.

    The Support Rep acknowledges the report, communicates
    investigation uncertainty, and requests missing information.

    It does not establish root causes, invent solutions,
    recommend unverified workarounds, or send messages.
    """

    _validate_findings(
        "receptionist_findings",
        receptionist_findings,
    )

    _validate_findings(
        "debugger_findings",
        debugger_findings,
    )

    title = _clean_text(
        getattr(ticket, "title", "")
    ) or "your reported issue"

    reporter_name = _clean_text(
        getattr(ticket, "reporter_name", "")
    )

    actual_behavior = _clean_text(
        getattr(ticket, "actual_behavior", "")
    )

    description = _clean_text(
        getattr(ticket, "description", "")
    )

    expected_behavior = _clean_text(
        getattr(ticket, "expected_behavior", "")
    )

    steps = _clean_text(
        getattr(ticket, "steps_to_reproduce", "")
    )

    evidence_references = _build_evidence_references(
        debugger_findings,
    )

    evidence_found = bool(evidence_references)

    follow_up_questions = _get_follow_up_questions(ticket)

    greeting = (
        f"Hello {reporter_name},"
        if reporter_name
        else "Hello,"
    )

    reported_behavior = (
        actual_behavior
        or description
        or title
    )

    lines = [
        greeting,
        "",
        "Thank you for reporting this issue.",
        "",
        f"We understand that {reported_behavior}",
    ]

    if expected_behavior:
        lines.append(
            f"You expected that {expected_behavior}"
        )

    if steps:
        lines.extend([
            "",
            f"You reported reproducing the issue by: {steps}",
        ])

    lines.append("")

    if evidence_found:
        lines.append(
            "We found documentation that may be related "
            "to your report. However, we have not yet "
            "confirmed that it explains this specific "
            "behaviour, so we do not want to present it "
            "as a verified cause or solution."
        )

    else:
        lines.append(
            "The information currently available to us "
            "is not sufficient to identify the underlying "
            "cause or recommend a confirmed fix."
        )

    if follow_up_questions:
        lines.extend([
            "",
            "To help us investigate further, could you "
            "please clarify the following:",
            "",
        ])

        for index, question in enumerate(
            follow_up_questions,
            start=1,
        ):
            lines.append(f"{index}. {question}")

    lines.extend([
        "",
        "Thank you for helping us investigate this issue. "
        "We will review the additional information before "
        "recommending a solution.",
        "",
        "Regards,",
        "Support Team",
    ])

    # These notes are internal and are not part of the draft.
    internal_review_notes = []

    category = receptionist_findings.get("category")
    priority = receptionist_findings.get("priority")

    if category or priority:
        internal_review_notes.append({
            "type": "classification",
            "category": category,
            "priority": priority,
            "instruction": (
                "Review the initial classification and "
                "priority before responding."
            ),
        })

    if evidence_found:
        internal_review_notes.append({
            "type": "documentation",
            "instruction": (
                "Review the retrieved documentation and "
                "confirm its relevance before using it "
                "to support technical guidance."
            ),
            "evidence_count": len(evidence_references),
        })

    else:
        internal_review_notes.append({
            "type": "insufficient_evidence",
            "instruction": (
                "No supporting documentation was retrieved. "
                "Do not suggest a technical cause or fix."
            ),
        })

    root_cause = debugger_findings.get(
        "root_cause",
        {},
    )

    root_cause_status = (
        root_cause.get("status", "unknown")
        if isinstance(root_cause, dict)
        else "unknown"
    )

    if root_cause_status != "established":
        internal_review_notes.append({
            "type": "root_cause",
            "status": root_cause_status,
            "instruction": (
                "The underlying cause has not been established."
            ),
        })

    return {
        "draft_status": "pending_human_review",

        "subject": f"Update on your report: {title}",

        "draft_response": "\n".join(lines),

        "response_type": (
            "acknowledgement_and_information_request"
            if follow_up_questions
            else "acknowledgement"
        ),

        "follow_up_questions": follow_up_questions,

        "evidence_references": evidence_references,

        "internal_review_notes": internal_review_notes,

        "requires_human_review": True,

        "external_send_authorized": False,

        "responder": {
            "name": "deterministic_support_rep",
            "version": SUPPORT_REP_VERSION,
        },
    }