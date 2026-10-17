from __future__ import annotations

from fastapi import Depends, Request

from app.core.container import Container
from app.core.security import AuthUser


def get_container(request: Request) -> Container:
    return request.app.state.container


def get_current_user(request: Request, container: Container = Depends(get_container)) -> AuthUser:
    user = container.authenticator.authenticate(request.headers.get("authorization"))
    known: set[str] = request.app.state.known_profiles
    if user.id not in known:
        # Supabase creates profiles with a sign-up trigger; this covers users created before
        # the migration ran (and test authenticators). Done once per user per process.
        container.repo.ensure_profile(user.id, (user.email or "").split("@")[0] or None)
        known.add(user.id)
    return user
