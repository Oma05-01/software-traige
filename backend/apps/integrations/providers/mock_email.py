import hashlib

from django.core.exceptions import ValidationError
from django.core.validators import validate_email


class MockEmailProvider:
    """
    Simulates an email provider.

    This adapter does not establish a network connection
    or send an actual email.
    """

    provider_name = "mock_email"

    def send(
        self,
        *,
        recipient,
        subject,
        body,
        idempotency_key,
    ):
        if not isinstance(recipient, str) or not recipient.strip():
            raise ValueError("A recipient email is required.")

        try:
            validate_email(recipient)
        except ValidationError as exc:
            raise ValueError("Invalid recipient email.") from exc

        if not isinstance(subject, str) or not subject.strip():
            raise ValueError("An email subject is required.")

        if not isinstance(body, str) or not body.strip():
            raise ValueError("An email body is required.")

        if not idempotency_key:
            raise ValueError("An idempotency key is required.")

        digest = hashlib.sha256(
            idempotency_key.encode("utf-8")
        ).hexdigest()[:20]

        return {
            "provider": self.provider_name,
            "delivery_mode": "mock",
            "accepted": True,
            "external_delivery_performed": False,
            "provider_message_id": f"mock-{digest}",
            "note": (
                "Mock execution successful. "
                "No external email was sent."
            ),
        }