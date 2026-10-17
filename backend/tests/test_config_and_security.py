import json
import logging
import sys
import types

import httpx
import pytest

from app.core.config import ConfigurationError, Settings
from app.core.errors import RateLimitedError, ServiceUnavailableError, StorageError, UnauthorizedError
from app.core.logging import RedactSecretsFilter
from app.core.security import LocalAuthenticator, RateLimiter, SupabaseAuthenticator
from app.services.embedding_service import SentenceTransformerEmbedder
from app.services.storage_service import LocalFileStorage, SupabaseStorage, object_key

SECRET = "sk-very-secret-value-123456"


def settings(**kw) -> Settings:
    return Settings(_env_file=None, **kw)


class TestConfiguration:
    def test_development_defaults_are_valid(self):
        settings().validate_for_startup()

    def test_production_requires_real_auth_database_and_storage(self):
        with pytest.raises(ConfigurationError) as exc:
            settings(app_env="production").validate_for_startup()
        message = str(exc.value)
        for name in ("AUTH_MODE", "DATABASE_BACKEND", "STORAGE_BACKEND"):
            assert name in message

    def test_missing_supabase_variables_are_named(self):
        with pytest.raises(ConfigurationError) as exc:
            settings(auth_mode="supabase", storage_backend="supabase", database_backend="postgres").validate_for_startup()
        message = str(exc.value)
        assert "SUPABASE_URL" in message and "SUPABASE_ANON_KEY" in message
        assert "SUPABASE_SERVICE_ROLE_KEY" in message and "DATABASE_URL" in message

    def test_gemini_key_and_model_must_be_set_together(self):
        with pytest.raises(ConfigurationError) as exc:
            settings(google_api_key=SECRET).validate_for_startup()
        assert "GEMINI_MODEL" in str(exc.value) and SECRET not in str(exc.value)

    def test_hashing_embedder_refused_in_production(self):
        with pytest.raises(ConfigurationError) as exc:
            settings(app_env="production", embedding_provider="hashing").validate_for_startup()
        assert "test-only" in str(exc.value)

    def test_secrets_are_not_rendered(self):
        s = settings(google_api_key=SECRET, gemini_model="m", supabase_service_role_key=SECRET)
        assert SECRET not in repr(s) and SECRET not in str(s.model_dump())
        assert s.gemini_configured

    def test_complete_production_configuration_is_valid(self):
        settings(
            app_env="production", auth_mode="supabase", database_backend="postgres", storage_backend="supabase",
            supabase_url="https://x.supabase.co", supabase_anon_key="anon", supabase_service_role_key="srv",
            database_url="postgresql://u:p@h/db", allowed_origins="https://app.example.com",
            embedding_provider="sentence-transformers",
        ).validate_for_startup()


def test_log_filter_redacts_secrets_and_tokens(caplog):
    logger = logging.getLogger("papertrail.test-redaction")
    handler = logging.StreamHandler()
    logs: list[str] = []
    handler.emit = lambda record: logs.append(record.getMessage())  # type: ignore[method-assign]
    handler.addFilter(RedactSecretsFilter([SECRET]))
    logger.addHandler(handler)
    logger.warning("key=%s auth=Bearer abc.def.ghi url=postgresql://user:hunter2@db/x", SECRET)
    logger.removeHandler(handler)
    assert SECRET not in logs[0] and "abc.def.ghi" not in logs[0] and "hunter2" not in logs[0]


class TestSupabaseAuthenticator:
    def make(self, handler):
        return SupabaseAuthenticator("https://proj.supabase.co", "anon-key", client=httpx.Client(transport=httpx.MockTransport(handler)))

    def test_valid_token_resolves_user_and_is_cached(self):
        calls = []

        def handler(request):
            calls.append(request)
            assert request.url.path == "/auth/v1/user"
            assert request.headers["apikey"] == "anon-key"
            return httpx.Response(200, json={"id": "user-1", "email": "u@example.com"})

        auth = self.make(handler)
        assert auth.authenticate("Bearer token-abc").id == "user-1"
        assert auth.authenticate("Bearer token-abc").email == "u@example.com"
        assert len(calls) == 1

    def test_rejected_token(self):
        auth = self.make(lambda r: httpx.Response(401, json={"msg": "bad jwt"}))
        with pytest.raises(UnauthorizedError):
            auth.authenticate("Bearer expired")

    @pytest.mark.parametrize("header", [None, "", "Basic abc", "Bearer "])
    def test_malformed_headers(self, header):
        auth = self.make(lambda r: httpx.Response(200, json={"id": "x"}))
        with pytest.raises(UnauthorizedError):
            auth.authenticate(header)

    def test_auth_service_outage(self):
        def handler(request):
            raise httpx.ConnectError("down")

        with pytest.raises(ServiceUnavailableError):
            self.make(handler).authenticate("Bearer t")


def test_local_authenticator_is_single_fixed_user():
    assert LocalAuthenticator().authenticate(None).auth_mode == "local"


def test_rate_limiter():
    limiter = RateLimiter()
    limiter.check("u", "verify", 2)
    limiter.check("u", "verify", 2)
    with pytest.raises(RateLimitedError):
        limiter.check("u", "verify", 2)
    limiter.check("other", "verify", 2)


class TestStorage:
    def test_object_keys_require_uuids(self):
        with pytest.raises(ValueError):
            object_key("../../etc", "passwd")

    def test_local_storage_round_trip_and_traversal_guard(self, tmp_path):
        storage = LocalFileStorage(tmp_path)
        key = object_key("11111111-1111-4111-8111-111111111111", "22222222-2222-4222-8222-222222222222")
        storage.save(key, b"%PDF-data")
        assert storage.load(key) == b"%PDF-data"
        storage.delete(key)
        with pytest.raises(StorageError):
            storage.load(key)
        with pytest.raises(StorageError):
            storage.load("../outside.pdf")

    def test_supabase_storage_uses_private_authenticated_endpoints(self):
        seen = []

        def handler(request):
            seen.append((request.method, request.url.path, request.headers.get("authorization")))
            if request.method == "GET":
                return httpx.Response(200, content=b"%PDF")
            if request.method == "DELETE":
                assert json.loads(request.content) == {"prefixes": ["a/b.pdf"]}
            return httpx.Response(200, json={})

        storage = SupabaseStorage("https://p.supabase.co", "service-key", "documents",
                                  client=httpx.Client(transport=httpx.MockTransport(handler)))
        storage.save("a/b.pdf", b"%PDF")
        assert storage.load("a/b.pdf") == b"%PDF"
        storage.delete("a/b.pdf")
        assert seen[0][:2] == ("POST", "/storage/v1/object/documents/a/b.pdf")
        assert seen[1][1] == "/storage/v1/object/authenticated/documents/a/b.pdf"
        assert all(auth == "Bearer service-key" for *_, auth in seen)

    def test_supabase_storage_errors_do_not_leak_bodies(self):
        storage = SupabaseStorage("https://p.supabase.co", "k", "documents",
                                  client=httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(500, text="internal secret"))))
        with pytest.raises(StorageError) as exc:
            storage.save("a/b.pdf", b"x")
        assert "internal secret" not in exc.value.message


def test_sentence_transformer_dimension_mismatch_is_detected(monkeypatch):
    class FakeModel:
        max_seq_length = 512

        def __init__(self, name, device):
            pass

        def get_sentence_embedding_dimension(self):
            return 768

    monkeypatch.setitem(sys.modules, "sentence_transformers", types.SimpleNamespace(SentenceTransformer=FakeModel))
    embedder = SentenceTransformerEmbedder("some/model", 384)
    with pytest.raises(ConfigurationError) as exc:
        embedder.embed_query("x")
    assert "768" in str(exc.value) and "EMBEDDING_DIMENSION" in str(exc.value)
