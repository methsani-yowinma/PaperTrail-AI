"""Authentication.

* ``LocalAuthenticator`` — explicit single-user development mode. Every request acts as one
  fixed local user. Refused at startup when APP_ENV=production.
* ``SupabaseAuthenticator`` — verifies the bearer access token by calling Supabase Auth's
  ``GET /auth/v1/user`` endpoint (the supported server-side verification path; no custom
  JWT handling). Successful lookups are cached briefly, keyed by a hash of the token.
"""

from __future__ import annotations

import hashlib
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Protocol

import httpx

from app.core.config import LOCAL_USER_ID
from app.core.errors import ServiceUnavailableError, UnauthorizedError


@dataclass(frozen=True)
class AuthUser:
    id: str
    email: str | None
    auth_mode: str


class Authenticator(Protocol):
    mode: str

    def authenticate(self, authorization: str | None) -> AuthUser: ...


class LocalAuthenticator:
    mode = "local"

    def authenticate(self, authorization: str | None) -> AuthUser:
        return AuthUser(id=LOCAL_USER_ID, email=None, auth_mode="local")


def _bearer(authorization: str | None) -> str:
    if not authorization:
        raise UnauthorizedError("Sign in to continue.", code="missing_token")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise UnauthorizedError("Invalid authorization header.", code="invalid_token")
    return token.strip()


class SupabaseAuthenticator:
    mode = "supabase"

    def __init__(
        self, supabase_url: str, anon_key: str, *, client: httpx.Client | None = None, cache_seconds: float = 60.0,
        cache_size: int = 1024,
    ):
        self._endpoint = f"{supabase_url.rstrip('/')}/auth/v1/user"
        self._anon_key = anon_key
        self._client = client or httpx.Client(timeout=httpx.Timeout(10.0, connect=5.0))
        self._ttl = cache_seconds
        self._size = cache_size
        self._cache: OrderedDict[str, tuple[float, AuthUser]] = OrderedDict()
        self._lock = threading.Lock()

    def authenticate(self, authorization: str | None) -> AuthUser:
        token = _bearer(authorization)
        key = hashlib.sha256(token.encode()).hexdigest()
        now = time.monotonic()
        with self._lock:
            cached = self._cache.get(key)
            if cached and cached[0] > now:
                self._cache.move_to_end(key)
                return cached[1]
        try:
            response = self._client.get(self._endpoint, headers={"Authorization": f"Bearer {token}", "apikey": self._anon_key})
        except httpx.HTTPError as exc:
            raise ServiceUnavailableError("The authentication service is unreachable.", code="auth_unavailable") from exc
        if response.status_code in (401, 403):
            raise UnauthorizedError("Your session has expired. Please sign in again.", code="invalid_token")
        if response.status_code != 200:
            raise ServiceUnavailableError("The authentication service returned an error.", code="auth_unavailable")
        try:
            data = response.json()
        except ValueError:
            data = None
        if not isinstance(data, dict):
            # e.g. SUPABASE_URL points at something other than the Supabase API.
            raise ServiceUnavailableError("The authentication service returned an unexpected response.", code="auth_unavailable")
        user_id = data.get("id")
        if not user_id:
            raise UnauthorizedError("Invalid session.", code="invalid_token")
        user = AuthUser(id=str(user_id), email=data.get("email"), auth_mode="supabase")
        with self._lock:
            self._cache[key] = (now + self._ttl, user)
            while len(self._cache) > self._size:
                self._cache.popitem(last=False)
        return user


class RateLimiter:
    """In-memory sliding-window limiter, per user and action.

    Suitable for a single backend instance. With several instances, replace it with a
    shared store (documented in docs/SECURITY.md).
    """

    def __init__(self):
        self._events: dict[tuple[str, str], list[float]] = {}
        self._lock = threading.Lock()

    def check(self, user_id: str, action: str, limit_per_minute: int) -> None:
        from app.core.errors import RateLimitedError

        now = time.monotonic()
        with self._lock:
            events = [t for t in self._events.get((user_id, action), []) if now - t < 60.0]
            if len(events) >= limit_per_minute:
                self._events[(user_id, action)] = events
                raise RateLimitedError(f"Too many {action} requests. Please wait a minute and try again.")
            events.append(now)
            self._events[(user_id, action)] = events
