"""Logging setup with a redaction filter so secrets never reach log output."""

from __future__ import annotations

import logging
import re

from app.core.config import Settings

_PATTERNS = [
    re.compile(r"(Bearer\s+)[A-Za-z0-9\-._~+/]+=*", re.IGNORECASE),
    re.compile(r"(key=)[A-Za-z0-9\-_]{12,}", re.IGNORECASE),
    re.compile(r"(postgres(?:ql)?://[^:/\s]+:)[^@\s]+(@)", re.IGNORECASE),
    re.compile(r"(AIza)[A-Za-z0-9\-_]{20,}"),
]


class RedactSecretsFilter(logging.Filter):
    def __init__(self, secrets: list[str] | None = None):
        super().__init__()
        self._secrets = [s for s in (secrets or []) if s and len(s) >= 8]

    def _redact(self, text: str) -> str:
        for secret in self._secrets:
            text = text.replace(secret, "[REDACTED]")
        for pattern in _PATTERNS:
            if pattern.groups == 2:
                text = pattern.sub(r"\1[REDACTED]\2", text)
            else:
                text = pattern.sub(r"\1[REDACTED]", text)
        return text

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            message = record.getMessage()
        except Exception:  # pragma: no cover - malformed log call
            return True
        redacted = self._redact(message)
        if redacted != message:
            record.msg, record.args = redacted, ()
        return True


def configure_logging(settings: Settings) -> None:
    secrets = [
        s.get_secret_value()
        for s in (
            settings.google_api_key,
            settings.supabase_service_role_key,
            settings.supabase_anon_key,
            settings.database_url,
        )
        if s is not None
    ]
    root = logging.getLogger("papertrail")
    root.setLevel(settings.log_level.upper())
    if not any(isinstance(h, logging.StreamHandler) for h in root.handlers):
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
        root.addHandler(handler)
    for handler in root.handlers:
        handler.filters = [f for f in handler.filters if not isinstance(f, RedactSecretsFilter)]
        handler.addFilter(RedactSecretsFilter(secrets))
