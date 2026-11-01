import re

from apps.tickets.models import Ticket


BUG_SIGNALS = (
    "crash",
    "crashes",
    "crashed",
    "crashing",
    "error",
    "exception",
    "failure",
    "fails",
    "failed",
    "broken",
    "not working",
    "does not work",
    "doesn't work",
    "unable to",
    "cannot",
    "can't",
    "timeout",
    "freezes",
    "frozen",
    "incorrect",
    "malfunction",
    "bug",
    "typo",
)

FEATURE_SIGNALS = (
    "feature request",
    "would like the application to",
    "would like the system to",
    "would like to add",
    "would like support for",
    "would like a feature",
    "please add",
    "could you add",
    "add support",
    "new feature",
    "it would be useful",
    "allow users to",
    "requesting a feature",
    "request to add",
)

CRITICAL_SIGNALS = (
    "production outage",
    "production is down",
    "service is down",
    "complete outage",
    "data loss",
    "security breach",
    "all users are affected",
    "cannot access the system",
    "payment system unavailable",
)

HIGH_PRIORITY_SIGNALS = (
    "crash",
    "crashes",
    "crashed",
    "crashing",
    "blocking",
    "blocked",
    "unable to",
    "cannot",
    "can't",
    "not working",
    "failure",
    "fails",
    "exception",
    "timeout",
)

LOW_PRIORITY_SIGNALS = (
    "minor",
    "cosmetic",
    "typo",
    "spacing",
    "alignment",
    "colour",
    "color",
    "formatting",
)


def normalize_text(value):
    """Normalize text for consistent keyword matching."""

    return " ".join((value or "").lower().split())


def find_matches(text, signals):
    """Return all matching classification signals."""

    return [
        signal
        for signal in signals
        if re.search(
            r"(?<!\w)" + re.escape(signal) + r"(?!\w)",
            text,
        )
    ]


def extract_technical_details(text, ticket):
    """Extract basic technical information from a ticket."""

    file_types = re.findall(
        r"\b(PDF|CSV|DOCX|XLSX|JPEG|JPG|PNG|JSON|XML)\b",
        text,
        flags=re.IGNORECASE,
    )

    file_sizes = re.findall(
        r"\b\d+(?:\.\d+)?\s?(?:KB|MB|GB|TB)\b",
        text,
        flags=re.IGNORECASE,
    )

    return {
        "file_types": sorted({
            item.upper() for item in file_types
        }),
        "file_sizes": sorted({
            " ".join(item.upper().split())
            for item in file_sizes
        }),
        "environment": ticket.environment,
    }


def determine_category(text):
    """Determine the likely ticket category."""

    bug_matches = find_matches(text, BUG_SIGNALS)

    feature_matches = find_matches(text, FEATURE_SIGNALS)

    if bug_matches and feature_matches:
        return {
            "category": Ticket.Category.OTHER,
            "confidence": "low",
            "needs_human_review": True,
            "reasons": [
                "Both bug and feature indicators were found."
            ],
        }

    if bug_matches:
        return {
            "category": Ticket.Category.BUG,
            "confidence": "high",
            "needs_human_review": False,
            "reasons": [
                f"Matched bug indicator: {item}"
                for item in bug_matches
            ],
        }

    if feature_matches:
        return {
            "category": Ticket.Category.FEATURE,
            "confidence": "high",
            "needs_human_review": False,
            "reasons": [
                f"Matched feature indicator: {item}"
                for item in feature_matches
            ],
        }

    return {
        "category": Ticket.Category.OTHER,
        "confidence": "low",
        "needs_human_review": True,
        "reasons": [
            "Insufficient classification evidence."
        ],
    }


def determine_priority(text, category):
    """Recommend ticket priority based on explicit signals."""

    critical_matches = find_matches(
        text,
        CRITICAL_SIGNALS,
    )

    if critical_matches:
        return Ticket.Priority.CRITICAL

    high_matches = find_matches(
        text,
        HIGH_PRIORITY_SIGNALS,
    )

    if high_matches:
        return Ticket.Priority.HIGH

    low_matches = find_matches(
        text,
        LOW_PRIORITY_SIGNALS,
    )

    if low_matches:
        return Ticket.Priority.LOW

    if category == Ticket.Category.OTHER:
        return Ticket.Priority.UNASSESSED

    return Ticket.Priority.MEDIUM


def classify_ticket(ticket):
    """
    Deterministically classify a ticket.

    This implementation does not use an LLM.
    """

    raw_text = " ".join([
        ticket.title or "",
        ticket.description or "",
        ticket.environment or "",
        ticket.steps_to_reproduce or "",
        ticket.expected_behavior or "",
        ticket.actual_behavior or "",
    ])

    text = normalize_text(raw_text)

    classification = determine_category(text)

    category = classification["category"]

    priority = determine_priority(text, category)

    return {
        "category": category,
        "priority": priority,

        "issue_summary": ticket.title,

        "classification_confidence": (
            classification["confidence"]
        ),

        "needs_human_review": (
            classification["needs_human_review"]
        ),

        "classification_reasons": (
            classification["reasons"]
        ),

        "technical_details": extract_technical_details(
            raw_text,
            ticket,
        ),

        "classifier": {
            "name": "deterministic_receptionist",
            "version": "1.0.0",
        },
    }