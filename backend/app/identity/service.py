from __future__ import annotations

import re
import uuid
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

from email_validator import EmailNotValidError, validate_email
from sqlalchemy import func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.db import ACTOR_GUC, LOGIN_GUC, TOKEN_GUC, set_config, set_owner
from app.core.errors import ApiError
from app.core.security import (
    hash_password,
    hash_token,
    new_token,
    password_needs_rehash,
    verify_password_or_dummy,
)
from app.identity.emailer import EmailSender, OutboundEmail
from app.identity.models import AppSetting, EmailToken, PrivateRecord, Session, User

USERNAME = re.compile(r"[A-Za-z0-9_]{3,32}")
VERIFICATION_TTL = timedelta(hours=24)
RESET_TTL = timedelta(minutes=30)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def normalize_username(value: str) -> str:
    candidate = value.strip().lower()
    if not USERNAME.fullmatch(candidate):
        raise ApiError(
            422,
            "invalid_username",
            "Username must be 3–32 characters and use letters, numbers, or underscores.",
        )
    return candidate


def normalize_email(value: str) -> str:
    try:
        parsed = validate_email(value.strip(), check_deliverability=False)
    except EmailNotValidError as exc:
        raise ApiError(422, "invalid_email", "Enter a valid email address.") from exc
    return parsed.normalized.lower()


def validate_password(password: str, username: str) -> None:
    if not 12 <= len(password) <= 128:
        raise ApiError(422, "invalid_password", "Password must be 12 to 128 characters.")
    if password.lower() == username.lower():
        raise ApiError(422, "invalid_password", "Password must be different from the username.")


def _public_link(settings: Settings, path: str, token: str) -> str:
    return f"{settings.public_app_url}{path}?token={quote(token)}"


async def registration_enabled(session: AsyncSession) -> bool:
    row = await session.get(AppSetting, 1)
    return bool(row and row.registration_enabled)


async def _issue_token(
    session: AsyncSession,
    user: User,
    purpose: str,
    ttl: timedelta,
) -> str:
    now = utcnow()
    await set_owner(session, user.id)
    await session.execute(
        update(EmailToken)
        .where(
            EmailToken.user_id == user.id,
            EmailToken.purpose == purpose,
            EmailToken.consumed_at.is_(None),
        )
        .values(consumed_at=now)
    )
    raw = new_token()
    session.add(
        EmailToken(
            user_id=user.id,
            purpose=purpose,
            token_hash=hash_token(raw),
            expires_at=now + ttl,
        )
    )
    await session.flush()
    return raw


async def register_user(
    session: AsyncSession,
    settings: Settings,
    sender: EmailSender,
    *,
    username: str,
    email: str,
    password: str,
    requested_role: str | None,
) -> tuple[User, str, str]:
    if requested_role not in {None, "", "member"}:
        raise ApiError(403, "role_not_allowed", "Public registration cannot grant an administrator role.")
    if not await registration_enabled(session):
        raise ApiError(403, "registration_disabled", "Public registration is turned off.")
    username = normalize_username(username)
    email = normalize_email(email)
    validate_password(password, username)
    user = User(
        id=uuid.uuid4(),
        username=username,
        email=email,
        password_hash=hash_password(password),
        role="member",
    )
    await set_owner(session, user.id)
    session.add(user)
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise ApiError(409, "account_exists", "That username or email is already registered.") from exc
    raw = await _issue_token(session, user, "verification", VERIFICATION_TTL)
    delivery = await _send_verification(settings, sender, user, raw)
    return user, raw, delivery


async def _send_verification(settings: Settings, sender: EmailSender, user: User, raw: str) -> str:
    if settings.email_mode == "unconfigured":
        return "unconfigured"
    link = _public_link(settings, "/verify", raw)
    result = await sender.send(
        OutboundEmail(
            recipient=user.email,
            subject="Verify your SpendPilot email",
            body=(
                "Confirm this email address for SpendPilot.\n\n"
                f"{link}\n\n"
                "This link expires in 24 hours and can be used once. "
                "If you did not register, ignore this message."
            ),
        )
    )
    return result


async def resend_verification(
    session: AsyncSession,
    settings: Settings,
    sender: EmailSender,
    user: User,
) -> str:
    if user.email_verified_at is not None:
        return "already_verified"
    if settings.email_mode == "unconfigured":
        raise ApiError(
            409,
            "email_delivery_unconfigured",
            "Email delivery is not configured, so a verification message cannot be sent.",
        )
    raw = await _issue_token(session, user, "verification", VERIFICATION_TTL)
    return await _send_verification(settings, sender, user, raw)


async def authenticate(
    session: AsyncSession,
    *,
    identifier: str,
    password: str,
) -> User | None:
    ident = identifier.strip().lower()
    await set_config(session, LOGIN_GUC, ident)
    user = await session.scalar(
        select(User).where(or_(func.lower(User.username) == ident, func.lower(User.email) == ident))
    )
    if user is None or user.is_disabled:
        verify_password_or_dummy(None, password)
        return None
    if not verify_password_or_dummy(user.password_hash, password):
        return None
    if password_needs_rehash(user.password_hash):
        user.password_hash = hash_password(password)
    return user


async def open_session(session: AsyncSession, user: User) -> tuple[str, str]:
    raw_session = new_token()
    raw_csrf = new_token()
    now = utcnow()
    await set_owner(session, user.id)
    session.add(
        Session(
            user_id=user.id,
            token_hash=hash_token(raw_session),
            csrf_token_hash=hash_token(raw_csrf),
            created_at=now,
            last_activity_at=now,
        )
    )
    await session.flush()
    return raw_session, raw_csrf


async def take_token(
    session: AsyncSession,
    raw: str,
    purpose: str,
) -> tuple[User, EmailToken]:
    digest = hash_token(raw)
    await set_config(session, TOKEN_GUC, digest)
    token = await session.scalar(
        select(EmailToken).where(EmailToken.token_hash == digest, EmailToken.purpose == purpose)
    )
    if token is None:
        raise ApiError(400, "token_invalid", "This link is invalid.")
    if token.consumed_at is not None:
        raise ApiError(400, "token_used", "This link was already used.")
    if token.expires_at <= utcnow():
        raise ApiError(400, "token_expired", "This link has expired.")
    await set_owner(session, token.user_id)
    user = await session.get(User, token.user_id)
    if user is None or user.is_disabled:
        raise ApiError(400, "token_invalid", "This link is invalid.")
    return user, token


async def verify_email(session: AsyncSession, raw: str) -> User:
    user, token = await take_token(session, raw, "verification")
    now = utcnow()
    token.consumed_at = now
    if user.email_verified_at is None:
        user.email_verified_at = now
    return user


async def request_password_reset(
    session: AsyncSession,
    settings: Settings,
    sender: EmailSender,
    email: str,
) -> str:
    if not settings.password_reset_available:
        return "unavailable"
    try:
        normalized = normalize_email(email)
    except ApiError:
        return "accepted"
    await set_config(session, LOGIN_GUC, normalized)
    user = await session.scalar(select(User).where(func.lower(User.email) == normalized))
    if user is None or user.is_disabled:
        return "accepted"
    raw = await _issue_token(session, user, "reset", RESET_TTL)
    link = _public_link(settings, "/reset", raw)
    await sender.send(
        OutboundEmail(
            recipient=user.email,
            subject="Reset your SpendPilot password",
            body=(
                "A password reset was requested for SpendPilot.\n\n"
                f"{link}\n\n"
                "This link expires in 30 minutes and can be used once. "
                "If you did not ask for this, ignore this message."
            ),
        )
    )
    return "accepted"


async def reset_password(session: AsyncSession, raw: str, password: str) -> User:
    user, token = await take_token(session, raw, "reset")
    validate_password(password, user.username)
    now = utcnow()
    token.consumed_at = now
    user.password_hash = hash_password(password)
    user.updated_at = now
    await session.execute(
        update(Session)
        .where(Session.user_id == user.id, Session.revoked_at.is_(None))
        .values(revoked_at=now)
    )
    return user


async def revoke_session(session: AsyncSession, auth_session: Session) -> None:
    auth_session.revoked_at = utcnow()


async def unlock_session(session: AsyncSession, auth_session: Session, user: User, password: str) -> None:
    if not verify_password_or_dummy(user.password_hash, password):
        raise ApiError(401, "invalid_credentials", "The username or password is incorrect.")
    now = utcnow()
    auth_session.locked_at = None
    auth_session.last_activity_at = now


async def record_attempt(session: AsyncSession, action: str, subject: str) -> None:
    from sqlalchemy import text

    await session.execute(
        text(
            "INSERT INTO auth_attempts (action, subject, attempted_at) "
            "VALUES (:action, :subject, now())"
        ),
        {"action": action, "subject": subject},
    )


async def too_many_attempts(
    session: AsyncSession,
    action: str,
    subject: str,
    *,
    limit: int,
    window: timedelta,
) -> bool:
    from sqlalchemy import text

    count = await session.scalar(
        text(
            "SELECT COUNT(*) FROM auth_attempts "
            "WHERE action = :action AND subject = :subject AND attempted_at >= :cutoff"
        ),
        {"action": action, "subject": subject, "cutoff": utcnow() - window},
    )
    return int(count or 0) >= limit


async def set_registration_enabled(session: AsyncSession, enabled: bool) -> None:
    await set_config(session, ACTOR_GUC, "admin")
    row = await session.get(AppSetting, 1)
    if row is None:
        raise ApiError(500, "settings_missing", "Installation settings are missing.")
    row.registration_enabled = enabled
    row.updated_at = utcnow()


async def create_private_record(session: AsyncSession, owner_id, label: str) -> PrivateRecord:
    cleaned = label.strip()
    if not 1 <= len(cleaned) <= 200:
        raise ApiError(422, "invalid_label", "The label must be 1 to 200 characters.")
    await set_owner(session, owner_id)
    record = PrivateRecord(owner_id=owner_id, label=cleaned)
    session.add(record)
    await session.flush()
    return record


async def list_private_records(session: AsyncSession, owner_id) -> list[PrivateRecord]:
    await set_owner(session, owner_id)
    rows = await session.scalars(
        select(PrivateRecord).where(PrivateRecord.owner_id == owner_id).order_by(PrivateRecord.created_at)
    )
    return list(rows)


async def get_private_record(session: AsyncSession, owner_id, record_id) -> PrivateRecord:
    await set_owner(session, owner_id)
    record = await session.get(PrivateRecord, record_id)
    if record is None:
        raise ApiError(404, "not_found", "That record does not exist.")
    return record
