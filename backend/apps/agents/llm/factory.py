from django.conf import settings

from apps.agents.llm.base import LLMConfigurationError


def get_llm_provider():
    """Return the configured LLM provider."""

    provider_name = settings.LLM_PROVIDER.lower()

    if provider_name == "groq":
        from apps.agents.llm.groq_provider import GroqProvider

        return GroqProvider()

    raise LLMConfigurationError(
        f"Unsupported LLM provider: {provider_name}"
    )