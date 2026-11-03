import json
import logging

from django.conf import settings
from groq import Groq

from apps.agents.llm.base import (
    LLMConfigurationError,
    LLMProviderError,
)


logger = logging.getLogger(__name__)


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

            raise LLMProviderError(
                f"Groq request failed: {type(exc).__name__}."
            ) from exc

        if not completion.choices:
            raise LLMProviderError(
                "Groq returned no completion choices."
            )

        choice = completion.choices[0]

        if choice.finish_reason == "length":
            raise LLMProviderError(
                "Groq response reached its completion token limit."
            )

        content = choice.message.content

        if not content:
            raise LLMProviderError(
                "Groq returned an empty response."
            )

        try:
            result = json.loads(content)

        except json.JSONDecodeError as exc:
            raise LLMProviderError(
                "Groq returned invalid JSON."
            ) from exc

        if not isinstance(result, dict):
            raise LLMProviderError(
                "Groq response must be a JSON object."
            )

        return result