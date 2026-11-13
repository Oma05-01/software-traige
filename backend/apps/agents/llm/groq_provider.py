
import json
import logging

import groq
from django.conf import settings
from groq import Groq

from apps.agents.llm.base import (
    LLMConfigurationError,
    LLMProviderError,
    LLMRequestError,
    LLMResponseError,
    LLMTransientError,
)


logger = logging.getLogger(__name__)


# These HTTP responses may represent temporary provider conditions.
TRANSIENT_HTTP_STATUS_CODES = {
    408,  # Request timeout
    409,  # Conflict
    425,  # Too early
    429,  # Rate limited
}


def is_transient_http_status(status_code):
    """Return whether an HTTP status is considered transient."""

    return (
        status_code in TRANSIENT_HTTP_STATUS_CODES
        or 500 <= status_code <= 599
    )


class GroqProvider:
    provider_name = "groq"

    def __init__(self):
        api_key = settings.GROQ_API_KEY

        if not api_key:
            raise LLMConfigurationError(
                "GROQ_API_KEY has not been configured."
            )

        self.model_name = settings.GROQ_MODEL

        self.client = Groq(
            api_key=api_key,
            timeout=settings.LLM_TIMEOUT_SECONDS,
            max_retries=settings.LLM_MAX_RETRIES,
        )

    def generate_structured(
        self,
        *,
        messages,
        schema_name,
        schema,
    ):
        """Generate and parse a strict JSON-schema response."""

        try:
            completion = self.client.chat.completions.create(
                model=self.model_name,
                messages=list(messages),
                max_completion_tokens=(
                    settings.LLM_MAX_COMPLETION_TOKENS
                ),
                reasoning_effort="low",
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": schema_name,
                        "strict": True,
                        "schema": schema,
                    },
                },
            )

        except Exception as exc:
            logger.exception(
                "Groq structured completion failed. Model=%s",
                self.model_name,
            )

            # Connection errors include APITimeoutError.
            if isinstance(exc, groq.APIConnectionError):
                raise LLMTransientError(
                    f"Groq connection failed: {type(exc).__name__}."
                ) from exc

            # APIStatusError includes RateLimitError and
            # InternalServerError. Classify using HTTP status.
            if isinstance(exc, groq.APIStatusError):
                status_code = exc.status_code

                if is_transient_http_status(status_code):
                    raise LLMTransientError(
                        f"Groq returned transient HTTP "
                        f"status {status_code}."
                    ) from exc

                raise LLMRequestError(
                    f"Groq rejected the request with "
                    f"HTTP status {status_code}."
                ) from exc

            # Unknown SDK/provider errors are not automatically
            # considered safe to retry.
            raise LLMProviderError(
                f"Groq request failed: {type(exc).__name__}."
            ) from exc

        if not completion.choices:
            raise LLMResponseError(
                "Groq returned no completion choices."
            )

        choice = completion.choices[0]

        if choice.finish_reason == "length":
            raise LLMResponseError(
                "Groq response reached its completion token limit."
            )

        content = choice.message.content

        if not content:
            raise LLMResponseError(
                "Groq returned an empty response."
            )

        try:
            result = json.loads(content)

        except json.JSONDecodeError as exc:
            raise LLMResponseError(
                "Groq returned invalid JSON."
            ) from exc

        if not isinstance(result, dict):
            raise LLMResponseError(
                "Groq response must be a JSON object."
            )

        return result
