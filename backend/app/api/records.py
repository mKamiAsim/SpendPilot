from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Request
from pydantic import BaseModel

from app.identity.routes import current_user
from app.identity.service import create_private_record, get_private_record, list_private_records

router = APIRouter(prefix="/api/v1/private-records", tags=["isolation"])


class RecordBody(BaseModel):
    label: str


def _dump(record) -> dict:
    return {
        "id": str(record.id),
        "owner_id": str(record.owner_id),
        "label": record.label,
    }


@router.get("")
async def list_records(request: Request) -> dict:
    user, _session = await current_user(request)
    rows = await list_private_records(request.state.db, user.id)
    return {"records": [_dump(row) for row in rows]}


@router.post("", status_code=201)
async def create_record(body: RecordBody, request: Request) -> dict:
    user, _session = await current_user(request)
    record = await create_private_record(request.state.db, user.id, body.label)
    return _dump(record)


@router.get("/{record_id}")
async def read_record(record_id: UUID, request: Request) -> dict:
    user, _session = await current_user(request)
    record = await get_private_record(request.state.db, user.id, record_id)
    return _dump(record)
