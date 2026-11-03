from typing import Protocol, Sequence


class LLMProviderError(Exception):
    """Base exception for LLM provider failures."""


class LLMConfigurationError(LLMProviderError):
    """Raised when an LLM provider is incorrectly configured."""


class LLMProvider(Protocol):
    """Interface implemented by every LLM provider."""

    provider_name: str
    model_name: str

    def generate_structured(
        self,
        *,
        messages: Sequence[dict[str, str]],
        schema_name: str,
        schema: dict,
    ) -> dict:
        """Generate a response conforming to a JSON schema."""
        ...