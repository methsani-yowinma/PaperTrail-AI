"""Shared fixtures. The suite needs no network, no Gemini key and no embedding-model download."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any, Callable

# Environment variables take precedence over backend/.env, so a developer's local
# configuration can never leak into (or break) the test run.
os.environ.update(
    {
        "APP_ENV": "test",
        "AUTH_MODE": "local",
        "DATABASE_BACKEND": "sqlite",
        "STORAGE_BACKEND": "local",
        "EMBEDDING_PROVIDER": "hashing",
        "GOOGLE_API_KEY": "",
        "GEMINI_MODEL": "",
        "DATABASE_URL": "",
    }
)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.core.config import Settings  # noqa: E402
from app.core.container import build_container  # noqa: E402
from app.core.errors import UnauthorizedError  # noqa: E402
from app.core.security import AuthUser  # noqa: E402
from app.main import create_app  # noqa: E402
from app.repositories.sqlite_repository import SQLiteRepository  # noqa: E402
from app.services.embedding_service import HashingEmbedder  # noqa: E402
from app.services.llm_client import LLMResponse  # noqa: E402
from app.services.storage_service import LocalFileStorage  # noqa: E402

ALICE = "11111111-1111-4111-8111-111111111111"
BOB = "22222222-2222-4222-8222-222222222222"


class TokenAuthenticator:
    """Test authenticator: 'Bearer alice' / 'Bearer bob'. Anything else is rejected."""

    mode = "supabase"
    users = {"alice": ALICE, "bob": BOB}

    def authenticate(self, authorization: str | None) -> AuthUser:
        if not authorization or not authorization.startswith("Bearer "):
            raise UnauthorizedError("Sign in to continue.", code="missing_token")
        name = authorization.removeprefix("Bearer ").strip()
        if name not in self.users:
            raise UnauthorizedError("Invalid session.", code="invalid_token")
        return AuthUser(id=self.users[name], email=f"{name}@example.test", auth_mode="supabase")


Responder = Callable[[dict[str, Any]], dict[str, Any] | str]


@dataclass
class FakeLLM:
    """Deterministic stand-in for Gemini. `responder` receives the parsed JSON payload."""

    responder: Responder
    explanation: str | None = "Explanation citing [P1]."
    model_identifier: str = "fake-llm-for-tests"
    calls: list[dict[str, Any]] = field(default_factory=list)
    fail_with: Exception | None = None

    def generate_json(self, *, system_instruction: str, contents: str, response_model) -> LLMResponse:
        self.calls.append({"system": system_instruction, "contents": contents, "schema": response_model.__name__})
        if self.fail_with:
            raise self.fail_with
        if response_model.__name__ == "LLMExplanationResponse":
            return LLMResponse(json.dumps({"explanation": self.explanation or ""}), {"prompt_tokens": 1})
        payload = json.loads(contents.split("\n\nYour previous answer")[0])
        result = self.responder(payload)
        return LLMResponse(result if isinstance(result, str) else json.dumps(result), {"prompt_tokens": 10})

    def check_model(self) -> dict[str, Any]:
        return {"model": self.model_identifier}


def keyword_responder(rules: dict[str, tuple[str, str, str, str]] | None = None) -> Responder:
    """Label each passage by the first rule phrase found in its text.

    rules: phrase -> (relation, directness, strength, evidence_type)
    """
    rules = rules or {
        "did not reduce overfitting": ("CONTRADICTS", "DIRECT", "STRONG", "EXPERIMENTAL_RESULT"),
        "reduced overfitting": ("SUPPORTS", "DIRECT", "STRONG", "EXPERIMENTAL_RESULT"),
        "reduces overfitting": ("SUPPORTS", "DIRECT", "MODERATE", "EXPERIMENTAL_RESULT"),
    }

    def respond(payload: dict[str, Any]) -> dict[str, Any]:
        out = []
        for p in payload["passages"]:
            text = p["text"]
            label = ("NOT_RELEVANT", "INDIRECT", "WEAK", "BACKGROUND_MENTION")
            quote = ""
            for phrase, value in rules.items():
                if phrase in text:
                    label = value
                    start = text.index(phrase)
                    quote = text[max(0, start - 20): start + len(phrase) + 20]
                    break
            out.append({
                "passage_id": p["passage_id"], "relation": label[0], "directness": label[1],
                "evidence_strength": label[2], "evidence_type": label[3], "rationale": f"Rule-based test label {label[0]}.",
                "quote": quote, "limitations": [], "confidence": 0.9,
            })
        return {"assessments": out}

    return respond


def make_settings(tmp_path, **overrides) -> Settings:
    values = dict(
        app_env="test",
        sqlite_path=tmp_path / "test.db",
        local_storage_dir=tmp_path / "uploads",
        embedding_provider="hashing",
        retrieval_min_semantic_similarity=0.35,
        rate_limit_verify_per_minute=100,
        rate_limit_upload_per_minute=100,
        google_api_key=None,
        gemini_model=None,
    )
    values.update(overrides)
    return Settings(_env_file=None, **values)


@pytest.fixture
def settings(tmp_path) -> Settings:
    return make_settings(tmp_path)


@pytest.fixture
def repo(settings):
    r = SQLiteRepository(settings.sqlite_path)
    for user in (ALICE, BOB):
        r.ensure_profile(user, None)
    yield r
    r.close()


@pytest.fixture
def fake_llm() -> FakeLLM:
    return FakeLLM(keyword_responder())


@pytest.fixture
def make_client(tmp_path):
    """Factory: make_client(llm=FakeLLM|None, **settings_overrides) -> TestClient."""
    clients: list[TestClient] = []

    def factory(llm: FakeLLM | None = None, **overrides) -> TestClient:
        s = make_settings(tmp_path, **overrides)
        container = build_container(
            s,
            repo=SQLiteRepository(s.sqlite_path),
            storage=LocalFileStorage(s.local_storage_dir),
            embedder=HashingEmbedder(s.embedding_dimension),
            llm=llm,
            use_configured_llm=False,
            authenticator=TokenAuthenticator(),
        )
        client = TestClient(create_app(container=container))
        client.__enter__()
        clients.append(client)
        return client

    yield factory
    for c in clients:
        c.__exit__(None, None, None)


@pytest.fixture
def client(make_client, fake_llm) -> TestClient:
    return make_client(llm=fake_llm)


AUTH_ALICE = {"Authorization": "Bearer alice"}
AUTH_BOB = {"Authorization": "Bearer bob"}


def upload(client: TestClient, pdf: bytes, name: str = "paper.pdf", headers=None, mime: str = "application/pdf"):
    return client.post(
        "/api/v1/documents/upload", files={"file": (name, pdf, mime)}, headers=headers or AUTH_ALICE
    )
