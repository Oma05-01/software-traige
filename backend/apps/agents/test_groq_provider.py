
from types import SimpleNamespace
from unittest.mock import Mock, patch

import groq
import httpx
from django.test import SimpleTestCase, override_settings

from apps.agents.llm.base import (
    LLMProviderError,
    LLMRequestError,
    LLMResponseError,
    LLMTransientError,
)
from apps.agents.llm.groq_provider import (
    GroqProvider,
    is_transient_http_status,
)


@override_settings(
    GROQ_API_KEY="test-api-key",
    GROQ_MODEL="test-model",
    LLM_TIMEOUT_SECONDS=10,
    LLM_MAX_RETRIES=1,
    LLM_MAX_COMPLETION_TOKENS=512,
)
class GroqProviderTests(SimpleTestCase):

    def setUp(self):
        self.client = Mock()

        self.groq_patch = patch(
            "apps.agents.llm.groq_provider.Groq",
            return_value=self.client,
        )
        self.groq_patch.start()
        self.addCleanup(self.groq_patch.stop)

        self.provider = GroqProvider()

        self.create_call = (
            self.client.chat.completions.create
        )

    def generate(self):
        return self.provider.generate_structured(
            messages=[],
            schema_name="test_schema",
            schema={"type": "object"},
        )

    @staticmethod
    def make_request():
        return httpx.Request(
            "POST",
            "https://api.groq.com/openai/v1/chat/completions",
        )

    @classmethod
    def make_status_error(
        cls,
        error_class,
        status_code,
    ):
        request = cls.make_request()

        response = httpx.Response(
            status_code,
            request=request,
        )

        return error_class(
            "Test provider error",
            response=response,
            body=None,
        )

    @staticmethod
    def make_completion(
        content,
        finish_reason="stop",
    ):
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    finish_reason=finish_reason,
                    message=SimpleNamespace(
                        content=content,
                    ),
                )
            ]
        )

    def test_connection_errors_are_transient(self):
        request = self.make_request()

        errors = [
            groq.APIConnectionError(request=request),
            groq.APITimeoutError(request=request),
        ]

        for error in errors:
            with self.subTest(error=type(error).__name__):
                self.create_call.side_effect = error

                with self.assertRaises(
                    LLMTransientError
                ) as context:
                    self.generate()

                self.assertIs(
                    context.exception.__cause__,
                    error,
                )

    def test_rate_limit_is_transient(self):
        error = self.make_status_error(
            groq.RateLimitError,
            429,
        )

        self.create_call.side_effect = error

        with self.assertRaises(LLMTransientError):
            self.generate()

    def test_server_errors_are_transient(self):
        error = self.make_status_error(
            groq.InternalServerError,
            500,
        )

        self.create_call.side_effect = error

        with self.assertRaises(LLMTransientError):
            self.generate()

    def test_selected_http_statuses_are_transient(self):
        transient_statuses = [
            408,
            409,
            425,
            429,
            500,
            502,
            503,
            504,
        ]

        for status_code in transient_statuses:
            with self.subTest(status_code=status_code):
                self.assertTrue(
                    is_transient_http_status(status_code)
                )

    def test_authentication_error_is_not_transient(self):
        error = self.make_status_error(
            groq.AuthenticationError,
            401,
        )

        self.create_call.side_effect = error

        with self.assertRaises(LLMRequestError):
            self.generate()

    def test_bad_request_is_not_transient(self):
        error = self.make_status_error(
            groq.BadRequestError,
            400,
        )

        self.create_call.side_effect = error

        with self.assertRaises(LLMRequestError):
            self.generate()

    def test_unknown_sdk_error_is_not_transient(self):
        error = groq.APIError(
            "Unexpected SDK error",
            request=self.make_request(),
            body=None,
        )

        self.create_call.side_effect = error

        with self.assertRaises(LLMProviderError) as context:
            self.generate()

        self.assertNotIsInstance(
            context.exception,
            LLMTransientError,
        )

    def test_empty_completion_is_response_error(self):
        self.create_call.return_value = SimpleNamespace(
            choices=[]
        )

        with self.assertRaises(LLMResponseError):
            self.generate()

    def test_token_limit_is_response_error(self):
        self.create_call.return_value = self.make_completion(
            '{"result": "partial"}',
            finish_reason="length",
        )

        with self.assertRaises(LLMResponseError):
            self.generate()

    def test_empty_content_is_response_error(self):
        self.create_call.return_value = self.make_completion("")

        with self.assertRaises(LLMResponseError):
            self.generate()

    def test_invalid_json_is_response_error(self):
        self.create_call.return_value = self.make_completion(
            "not valid JSON"
        )

        with self.assertRaises(LLMResponseError):
            self.generate()

    def test_non_object_json_is_response_error(self):
        self.create_call.return_value = self.make_completion(
            '["not", "an", "object"]'
        )

        with self.assertRaises(LLMResponseError):
            self.generate()

    def test_valid_json_response_succeeds(self):
        self.create_call.return_value = self.make_completion(
            '{"category": "bug"}'
        )

        result = self.generate()

        self.assertEqual(
            result,
            {"category": "bug"},
        )
