from __future__ import annotations

import secrets
from datetime import timedelta

from fastapi import Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.db import SESSION_GUC, set_config, set_owner
from app.core.errors import ApiError
from app.core.security import hash_token
from app.identity.models import Session, User
from app.identity.service import utcnow

SESSION_COOKIE = "spendpilot_session"
CSRF_COOKIE = "spendpilot_csrf"
ACTIVITY_EXEMPT_PATHS = {"/api/v1/auth/heartbeat", "/api/v1/events"}
LOCKED_OK_PATHS = {"/api/v1/auth/logout", "/api/v1/auth/unlock"}


def client_ip(request: Request, settings: Settings) -> str:
    if settings.trust_proxy:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip() or "unknown"
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def enforce_csrf(request: Request, settings: Settings) -> None:
    if request.method in {"GET", "HEAD", "OPTIONS"}:
        return
    if not request.url.path.startswith("/api/"):
        return
    header = request.headers.get("x-csrf-token") or ""
    cookie = request.cookies.get(CSRF_COOKIE) or ""
    if not header or not cookie or len(header) != len(cookie) or not secrets.compare_digest(header, cookie):
        raise ApiError(403, "csrf_failed", "The request failed the CSRF check.")
    origin = request.headers.get("origin")
    if origin and origin not in settings.allowed_origin_list:
        raise ApiError(403, "origin_rejected", "This origin is not allowed.")


async def load_session(
    request: Request,
    db: AsyncSession,
    *,
    allow_locked: bool,
    count_activity: bool,
) -> tuple[User, Session]:
    settings = get_settings()
    raw = request.cookies.get(SESSION_COOKIE)
    if not raw:
        raise ApiError(401, "unauthenticated", "Sign in to continue.")
    header = request.headers.get("x-csrf-token") or ""
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        digest = hash_token(header)
    else:
        digest = None
    token_hash = hash_token(raw)
    await set_config(db, SESSION_GUC, token_hash)
    auth_session = await db.scalar(
        select(Session).where(Session.token_hash == token_hash, Session.revoked_at.is_(None))
    )
    if auth_session is None:
        raise ApiError(401, "unauthenticated", "Sign in to continue.")
    if digest is not None and not secrets.compare_digest(digest, auth_session.csrf_token_hash):
        raise ApiError(403, "csrf_failed", "The request failed the CSRF check.")
    await set_owner(db, auth_session.user_id)
    user = await db.get(User, auth_session.user_id)
    if user is None or user.is_disabled:
        raise ApiError(401, "unauthenticated", "Sign in to continue.")
    now = utcnow()
    idle = timedelta(minutes=settings.idle_lock_minutes)
    is_idle = now - auth_session.last_activity_at > idle
    if auth_session.locked_at is not None or is_idle:
        if auth_session.locked_at is None:
            auth_session.locked_at = now
        if not allow_locked:
            raise ApiError(
                423,
                "session_locked",
                "This session is locked. Enter your password to continue.",
            )
    elif count_activity:
        auth_session.last_activity_at = now
    return user, auth_session
