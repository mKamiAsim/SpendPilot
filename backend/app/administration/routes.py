from __future__ import annotations

from fastapi import APIRouter, Request
from pydantic import BaseModel

from app.core.db import ACTOR_GUC, set_config
from app.core.errors import ApiError
from app.identity.models import AppSetting
from app.identity.routes import current_user
from app.identity.service import set_registration_enabled

router = APIRouter(prefix="/api/v1/admin", tags=["administration"])


class RegistrationBody(BaseModel):
    enabled: bool


async def require_admin(request: Request):
    user, _session = await current_user(request)
    if user.role != "admin":
        raise ApiError(403, "admin_required", "This action is only available to an administrator.")
    await set_config(request.state.db, ACTOR_GUC, "admin")
    return user


@router.get("/registration")
async def read_registration(request: Request) -> dict:
    await require_admin(request)
    row = await request.state.db.get(AppSetting, 1)
    return {"registration_enabled": bool(row and row.registration_enabled)}


@router.patch("/registration")
async def update_registration(body: RegistrationBody, request: Request) -> dict:
    await require_admin(request)
    await set_registration_enabled(request.state.db, body.enabled)
    return {"registration_enabled": body.enabled}


@router.get("/status")
async def admin_status(request: Request) -> dict:
    """Operational metadata only. No financial records."""

    from sqlalchemy import text

    from app.core.config import get_settings

    await require_admin(request)
    settings = get_settings()
    queue = await request.state.db.scalar(text("SELECT to_regclass('public.procrastinate_jobs')"))
    return {
        "database": "ok",
        "email_delivery": settings.email_mode,
        "queue_schema": "present" if queue else "missing",
        "worker_liveness": "unverified",
    }
