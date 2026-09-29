from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    CSRF_COOKIE,
    LOCKED_OK_PATHS,
    SESSION_COOKIE,
    ACTIVITY_EXEMPT_PATHS,
    client_ip,
    load_session,
)
from app.core.config import Settings, get_settings
from app.core.errors import ApiError
from app.core.security import hash_token
from app.identity.emailer import build_email_sender
from app.identity.models import User
from app.identity.service import (
    authenticate,
    open_session,
    record_attempt,
    registration_enabled,
    request_password_reset,
    resend_verification,
    reset_password,
    register_user,
    revoke_session,
    too_many_attempts,
    unlock_session,
    verify_email,
)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


class RegisterBody(BaseModel):
    username: str
    email: str
    password: str
    role: str | None = None


class LoginBody(BaseModel):
    username: str
    password: str


class TokenBody(BaseModel):
    token: str = Field(min_length=20, max_length=200)


class ResetBody(BaseModel):
    token: str = Field(min_length=20, max_length=200)
    password: str


class ForgotBody(BaseModel):
    email: str


class UnlockBody(BaseModel):
    password: str


def get_db(request: Request) -> AsyncSession:
    return request.state.db


def user_dict(user: User, *, session_locked: bool = False) -> dict:
    return {
        "id": str(user.id),
        "username": user.username,
        "email": user.email,
        "role": user.role,
        "email_verified": user.email_verified_at is not None,
        "session_locked": session_locked,
    }


def _cookies(response: Response, settings: Settings, raw_session: str, raw_csrf: str) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        raw_session,
        httponly=True,
        secure=settings.use_secure_cookies,
        samesite="lax",
        path="/",
    )
    response.set_cookie(
        CSRF_COOKIE,
        raw_csrf,
        httponly=False,
        secure=settings.use_secure_cookies,
        samesite="lax",
        path="/",
    )


def _clear_cookies(response: Response, settings: Settings) -> None:
    response.delete_cookie(SESSION_COOKIE, path="/", secure=settings.use_secure_cookies, samesite="lax")
    response.delete_cookie(CSRF_COOKIE, path="/", secure=settings.use_secure_cookies, samesite="lax")


async def current_user(request: Request) -> tuple[User, object]:
    path = request.url.path
    user, auth_session = await load_session(
        request,
        request.state.db,
        allow_locked=path in LOCKED_OK_PATHS,
        count_activity=path not in ACTIVITY_EXEMPT_PATHS and path not in LOCKED_OK_PATHS,
    )
    request.state.user = user
    request.state.auth_session = auth_session
    return user, auth_session


@router.get("/csrf")
async def issue_csrf(request: Request, response: Response, settings: Settings = Depends(get_settings)) -> dict:
    from sqlalchemy import select

    from app.core.db import SESSION_GUC, set_config, set_owner
    from app.core.security import hash_token, new_token
    from app.identity.models import Session

    token = new_token()
    raw_session = request.cookies.get(SESSION_COOKIE)
    if raw_session:
        await set_config(request.state.db, SESSION_GUC, hash_token(raw_session))
        auth_session = await request.state.db.scalar(
            select(Session).where(
                Session.token_hash == hash_token(raw_session),
                Session.revoked_at.is_(None),
            )
        )
        if auth_session is not None:
            await set_owner(request.state.db, auth_session.user_id)
            auth_session.csrf_token_hash = hash_token(token)
    response.set_cookie(
        CSRF_COOKIE,
        token,
        httponly=False,
        secure=settings.use_secure_cookies,
        samesite="lax",
        path="/",
    )
    return {"csrf_token": token}


@router.get("/options")
async def auth_options(request: Request, settings: Settings = Depends(get_settings)) -> dict:
    return {
        "registration_enabled": await registration_enabled(request.state.db),
        "password_reset_available": settings.password_reset_available,
        "email_delivery": settings.email_mode,
        "idle_lock_minutes": settings.idle_lock_minutes,
        "product_name": "SpendPilot",
    }


@router.post("/register", status_code=201)
async def register(body: RegisterBody, request: Request, response: Response) -> dict:
    settings = get_settings()
    db: AsyncSession = request.state.db
    user, _raw, delivery = await register_user(
        db,
        settings,
        build_email_sender(settings, db),
        username=body.username,
        email=body.email,
        password=body.password,
        requested_role=body.role,
    )
    raw_session, raw_csrf = await open_session(db, user)
    _cookies(response, settings, raw_session, raw_csrf)
    return {"user": user_dict(user), "email_delivery": delivery, "csrf_token": raw_csrf}


@router.post("/login")
async def login(body: LoginBody, request: Request, response: Response) -> dict:
    settings = get_settings()
    db: AsyncSession = request.state.db
    subject = hash_token(f"{client_ip(request, settings)}|{body.username.strip().lower()}")
    if await too_many_attempts(db, "login", subject, limit=10, window=timedelta(minutes=15)):
        raise ApiError(429, "rate_limited", "Too many attempts. Try again later.")
    user = await authenticate(db, identifier=body.username, password=body.password)
    if user is None:
        await record_attempt(db, "login", subject)
        raise ApiError(401, "invalid_credentials", "The username or password is incorrect.")
    raw_session, raw_csrf = await open_session(db, user)
    _cookies(response, settings, raw_session, raw_csrf)
    return {"user": user_dict(user), "csrf_token": raw_csrf}


@router.post("/logout")
async def logout(request: Request, response: Response) -> dict:
    user, auth_session = await current_user(request)
    await revoke_session(request.state.db, auth_session)
    _clear_cookies(response, get_settings())
    return {"signed_out": True, "user_id": str(user.id)}


@router.post("/verify")
async def verify(body: TokenBody, request: Request) -> dict:
    user = await verify_email(request.state.db, body.token)
    return {"user": user_dict(user)}


@router.post("/resend-verification")
async def resend(request: Request) -> dict:
    user, _session = await current_user(request)
    settings = get_settings()
    delivery = await resend_verification(
        request.state.db,
        settings,
        build_email_sender(settings, request.state.db),
        user,
    )
    return {"email_delivery": delivery}


@router.post("/forgot-password")
async def forgot(body: ForgotBody, request: Request) -> dict:
    settings = get_settings()
    db: AsyncSession = request.state.db
    if not settings.password_reset_available:
        return {
            "password_reset": "unavailable",
            "message": "Password reset stays off until email delivery is configured.",
        }
    subject = hash_token(client_ip(request, settings))
    if await too_many_attempts(db, "forgot", subject, limit=5, window=timedelta(hours=1)):
        raise ApiError(429, "rate_limited", "Too many attempts. Try again later.")
    await record_attempt(db, "forgot", subject)
    outcome = await request_password_reset(
        db,
        settings,
        build_email_sender(settings, db),
        body.email,
    )
    return {
        "password_reset": outcome,
        "message": "If an account exists for that address, a reset message will be sent.",
    }


@router.post("/reset-password")
async def reset(body: ResetBody, request: Request, response: Response) -> dict:
    user = await reset_password(request.state.db, body.token, body.password)
    _clear_cookies(response, get_settings())
    return {"password_reset": "completed", "user": user_dict(user)}


@router.post("/unlock")
async def unlock(body: UnlockBody, request: Request) -> dict:
    user, auth_session = await current_user(request)
    await unlock_session(request.state.db, auth_session, user, body.password)
    return {"user": user_dict(user, session_locked=False)}


@router.post("/heartbeat")
async def heartbeat(request: Request) -> dict:
    await current_user(request)
    return {"activity": "ignored"}


@router.get("/session")
async def session_view(request: Request) -> dict:
    user, auth_session = await current_user(request)
    locked = auth_session.locked_at is not None
    return {"user": user_dict(user, session_locked=locked)}
