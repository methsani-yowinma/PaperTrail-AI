"""GeminiClient error handling, using a fake SDK client (no network, no API key)."""

from types import SimpleNamespace

import httpx
import pytest
from google.genai import errors

from app.services.claim_assessment_service import LLMAssessmentResponse
from app.services.llm_client import GeminiClient, LLMError


class FakeModels:
    def __init__(self, result=None, exc=None):
        self.result, self.exc, self.kwargs = result, exc, None

    def generate_content(self, **kwargs):
        self.kwargs = kwargs
        if self.exc:
            raise self.exc
        return self.result

    def get(self, *, model):
        if self.exc:
            raise self.exc
        return SimpleNamespace(name=f"models/{model}", display_name="Fake", supported_actions=["generateContent"])


def client_with(models: FakeModels) -> GeminiClient:
    client = GeminiClient("test-key-not-real", "configured-model", timeout_seconds=5, max_retries=1)
    client._client = SimpleNamespace(models=models)
    return client


def call(client: GeminiClient):
    return client.generate_json(system_instruction="sys", contents="{}", response_model=LLMAssessmentResponse)


def test_successful_call_uses_structured_json_and_configured_model():
    usage = SimpleNamespace(prompt_token_count=12, candidates_token_count=5, thoughts_token_count=0)
    models = FakeModels(SimpleNamespace(text='{"assessments": []}', prompt_feedback=None, usage_metadata=usage))
    response = call(client_with(models))
    assert response.text == '{"assessments": []}'
    assert response.usage["prompt_tokens"] == 12
    config = models.kwargs["config"]
    assert models.kwargs["model"] == "configured-model"
    assert config.response_mime_type == "application/json"
    assert config.temperature == 0.0


@pytest.mark.parametrize(
    "exc, code",
    [
        (errors.ClientError(429, {"error": {"code": 429, "message": "quota", "status": "RESOURCE_EXHAUSTED"}}), "llm_rate_limited"),
        (errors.ClientError(404, {"error": {"code": 404, "message": "nf", "status": "NOT_FOUND"}}), "llm_model_unavailable"),
        (errors.ClientError(403, {"error": {"code": 403, "message": "denied", "status": "PERMISSION_DENIED"}}), "llm_auth_failed"),
        (errors.ServerError(503, {"error": {"code": 503, "message": "busy", "status": "UNAVAILABLE"}}), "llm_unavailable"),
        (httpx.ReadTimeout("slow"), "llm_timeout"),
        (httpx.ConnectError("down"), "llm_unreachable"),
        (RuntimeError("weird"), "llm_error"),
    ],
)
def test_provider_errors_are_translated(exc, code):
    with pytest.raises(LLMError) as raised:
        call(client_with(FakeModels(exc=exc)))
    assert raised.value.code == code
    assert "test-key-not-real" not in raised.value.message


def test_safety_block_is_reported():
    blocked = SimpleNamespace(text=None, prompt_feedback=SimpleNamespace(block_reason="SAFETY"), usage_metadata=None)
    with pytest.raises(LLMError) as raised:
        call(client_with(FakeModels(blocked)))
    assert raised.value.code == "llm_blocked"


def test_check_model_reports_details_and_errors():
    assert client_with(FakeModels())._client.models.get(model="m").name == "models/m"
    detail = client_with(FakeModels()).check_model()
    assert detail["resolved_name"] == "models/configured-model"
    with pytest.raises(LLMError):
        client_with(FakeModels(exc=errors.ClientError(404, {"error": {"code": 404, "message": "x"}}))).check_model()
