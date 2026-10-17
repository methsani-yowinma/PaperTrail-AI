"""Thin wrapper around the official Google Gen AI SDK (Gemini).

The wrapper only sends a request and returns raw JSON text plus usage numbers. Parsing,
validation and every decision about the output happen in ``claim_assessment_service``, so
the logic is testable with a fake client and no network access.

The API key is read from backend configuration only; it is never placed in prompts, logs
or responses.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Protocol

import httpx
from pydantic import BaseModel

from app.core.errors import ServiceUnavailableError

logger = logging.getLogger("papertrail.llm")


class LLMError(ServiceUnavailableError):
    code = "llm_unavailable"


@dataclass
class LLMResponse:
    text: str
    usage: dict[str, Any] = field(default_factory=dict)


class LLMClient(Protocol):
    model_identifier: str

    def generate_json(self, *, system_instruction: str, contents: str, response_model: type[BaseModel]) -> LLMResponse: ...

    def check_model(self) -> dict[str, Any]: ...


class GeminiClient:
    def __init__(self, api_key: str, model: str, *, timeout_seconds: float = 60.0, max_retries: int = 2):
        from google import genai
        from google.genai import types

        self._types = types
        self.model_identifier = model
        self._client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(
                timeout=int(timeout_seconds * 1000),
                retry_options=types.HttpRetryOptions(
                    attempts=max_retries + 1,
                    initial_delay=1.0,
                    max_delay=20.0,
                    http_status_codes=[408, 429, 500, 502, 503, 504],
                ),
            ),
        )

    def _translate(self, exc: Exception) -> LLMError:
        from google.genai import errors

        if isinstance(exc, errors.APIError):
            code = getattr(exc, "code", None)
            if code in (401, 403):
                return LLMError("Gemini rejected the API key or the key lacks access to this model.", code="llm_auth_failed")
            if code == 404:
                return LLMError(
                    f"The configured Gemini model '{self.model_identifier}' was not found or is not available to this key.",
                    code="llm_model_unavailable",
                )
            if code == 429:
                return LLMError("Gemini rate limit or quota reached. Try again later.", code="llm_rate_limited")
            if code == 400:
                return LLMError("Gemini rejected the request (HTTP 400).", code="llm_bad_request")
            return LLMError(f"Gemini is temporarily unavailable (HTTP {code}).", code="llm_unavailable")
        if isinstance(exc, httpx.TimeoutException):
            return LLMError("Gemini did not respond before the timeout.", code="llm_timeout")
        if isinstance(exc, httpx.HTTPError):
            return LLMError("Gemini could not be reached.", code="llm_unreachable")
        return LLMError("Gemini request failed unexpectedly.", code="llm_error")

    def generate_json(self, *, system_instruction: str, contents: str, response_model: type[BaseModel]) -> LLMResponse:
        config = self._types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=0.0,
            response_mime_type="application/json",
            response_schema=response_model,
            max_output_tokens=8192,
        )
        try:
            response = self._client.models.generate_content(model=self.model_identifier, contents=contents, config=config)
        except Exception as exc:
            translated = self._translate(exc)
            logger.warning("Gemini call failed: %s", translated.code)
            raise translated from exc

        feedback = getattr(response, "prompt_feedback", None)
        if feedback is not None and getattr(feedback, "block_reason", None):
            raise LLMError("Gemini declined to process this request (safety block).", code="llm_blocked")
        text = response.text or ""
        usage_meta = getattr(response, "usage_metadata", None)
        usage = {}
        if usage_meta is not None:
            usage = {
                "prompt_tokens": getattr(usage_meta, "prompt_token_count", None),
                "output_tokens": getattr(usage_meta, "candidates_token_count", None),
                "thinking_tokens": getattr(usage_meta, "thoughts_token_count", None),
            }
        return LLMResponse(text=text, usage=usage)

    def check_model(self) -> dict[str, Any]:
        try:
            model = self._client.models.get(model=self.model_identifier)
        except Exception as exc:
            raise self._translate(exc) from exc
        return {
            "model": self.model_identifier,
            "resolved_name": getattr(model, "name", None),
            "display_name": getattr(model, "display_name", None),
            "supported_actions": list(getattr(model, "supported_actions", None) or []),
        }
