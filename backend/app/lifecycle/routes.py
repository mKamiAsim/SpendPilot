"""Categories, instalments, backup, purge, and reconnectable events."""

from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import text

from app.core.errors import ApiError
from app.identity.routes import current_user
from app.ledger.money import money, money_str
from app.ledger.semantics import CATEGORIES
from app.lifecycle.backup import BackupError, export_payload, open_backup, restore_payload, seal_backup
from app.lifecycle.purge import purge_expired

router = APIRouter(prefix="/api/v1", tags=["lifecycle"])

LOCKED_CATEGORIES = (
    "Groceries",
    "Dining",
    "Transport",
    "Utilities",
    "Shopping",
    "Health",
    "Entertainment",
    "Travel",
    "Fees and interest",
    "Transfers",
    "Income",
    "Cash",
    "Other",
)


class CategoryBody(BaseModel):
    name: str = Field(min_length=1, max_length=40)


class InstalmentBody(BaseModel):
    description: str = Field(min_length=1, max_length=200)
    category: str = Field(min_length=1, max_length=40)
    principal: str
    parts: int = Field(ge=2, le=60)
    posted_on: str


class PartsBody(BaseModel):
    parts: int = Field(ge=2, le=60)


class RepaymentBody(BaseModel):
    posted_on: str
    amount: str


class BackupBody(BaseModel):
    passphrase: str = Field(min_length=8, max_length=128)
    include_secrets: bool = False


def _day(value: str) -> str:
    try:
        date.fromisoformat(value)
    except ValueError as exc:
        raise ApiError(422, "invalid_request", "Enter a date as YYYY-MM-DD.") from exc
    return value


def _positive(value: str) -> str:
    try:
        parsed = money(value)
    except Exception as exc:
        raise ApiError(422, "invalid_request", "Enter an amount.") from exc
    if parsed <= 0:
        raise ApiError(422, "invalid_request", "Enter an amount greater than zero.")
    return money_str(parsed)


async def category_allowed(db, name: str) -> bool:
    if name in CATEGORIES:
        return True
    found = await db.scalar(text("SELECT 1 FROM user_categories WHERE name = :name"), {"name": name})
    return found is not None


async def _require_category(db, name: str) -> None:
    if not await category_allowed(db, name):
        raise ApiError(422, "invalid_request", "Choose a category from the v1 list or one you added.")


def _monthly(principal, parts: int, repaid, repayment_count: int) -> str:
    if repayment_count <= 0:
        return money_str(money(principal) / parts)
    remaining_parts = parts - repayment_count
    if remaining_parts < 1:
        raise ApiError(422, "invalid_request", "Parts must still cover the repayments already recorded.")
    remaining = money(principal) - money(repaid)
    if remaining <= 0:
        return "0.00"
    return money_str(remaining / remaining_parts)


async def _record(db, owner_id, body: str) -> None:
    await db.execute(
        text("INSERT INTO user_events (owner_id, body) VALUES (:owner_id, :body)"),
        {"owner_id": owner_id, "body": body},
    )


@router.get("/categories")
async def list_categories(request: Request) -> dict:
    await current_user(request)
    result = await request.state.db.execute(text("SELECT name FROM user_categories ORDER BY name"))
    return {"categories": list(LOCKED_CATEGORIES), "custom": [row[0] for row in result]}


@router.post("/categories", status_code=201)
async def create_category(body: CategoryBody, request: Request) -> dict:
    user, _session = await current_user(request)
    name = " ".join(body.name.split())
    if name in CATEGORIES:
        raise ApiError(409, "category_exists", "That category is already in the v1 list.")
    if not name.replace(" ", "").isalnum():
        raise ApiError(422, "invalid_request", "A category name can use letters, numbers, and spaces.")
    category_id = uuid.uuid4()
    inserted = await request.state.db.execute(
        text(
            """
            INSERT INTO user_categories (id, owner_id, name)
            VALUES (:id, :owner_id, :name)
            ON CONFLICT (owner_id, name) DO NOTHING
            RETURNING id
            """
        ),
        {"id": category_id, "owner_id": user.id, "name": name},
    )
    if inserted.first() is None:
        raise ApiError(409, "category_exists", "That category already exists.")
    return {"id": str(category_id), "name": name}


@router.post("/instalments", status_code=201)
async def create_instalment(body: InstalmentBody, request: Request) -> dict:
    user, _session = await current_user(request)
    await _require_category(request.state.db, body.category)
    principal = _positive(body.principal)
    posted_on = _day(body.posted_on)
    monthly = _monthly(principal, body.parts, 0, 0)
    plan_id = uuid.uuid4()
    await request.state.db.execute(
        text(
            """
            INSERT INTO instalment_plans (
                id, owner_id, description, category, principal, parts, monthly_amount, posted_on
            ) VALUES (
                :id, :owner_id, :description, :category, :principal, :parts, :monthly_amount, :posted_on
            )
            """
        ),
        {
            "id": plan_id,
            "owner_id": user.id,
            "description": body.description.strip(),
            "category": body.category,
            "principal": principal,
            "parts": body.parts,
            "monthly_amount": monthly,
            "posted_on": posted_on,
        },
    )
    await _record(request.state.db, user.id, "instalment_created")
    return await _plan(request, plan_id)


@router.patch("/instalments/{plan_id}")
async def update_instalment(plan_id: uuid.UUID, body: PartsBody, request: Request) -> dict:
    await current_user(request)
    plan = await _load_plan(request, plan_id)
    repaid, count = await _repaid(request, plan_id)
    monthly = _monthly(plan["principal"], body.parts, repaid, count)
    await request.state.db.execute(
        text("UPDATE instalment_plans SET parts = :parts, monthly_amount = :monthly WHERE id = :id"),
        {"parts": body.parts, "monthly": monthly, "id": plan_id},
    )
    return await _plan(request, plan_id)


@router.post("/instalments/{plan_id}/repayments", status_code=201)
async def add_repayment(plan_id: uuid.UUID, body: RepaymentBody, request: Request) -> dict:
    user, _session = await current_user(request)
    plan = await _load_plan(request, plan_id)
    amount = _positive(body.amount)
    posted_on = _day(body.posted_on)
    repaid, count = await _repaid(request, plan_id)
    remaining = money(plan["principal"]) - money(repaid)
    if money(amount) > remaining:
        raise ApiError(422, "invalid_request", "A repayment cannot be more than the remaining principal.")
    repayment_id = uuid.uuid4()
    await request.state.db.execute(
        text(
            """
            INSERT INTO instalment_repayments (id, owner_id, plan_id, posted_on, amount)
            VALUES (:id, :owner_id, :plan_id, :posted_on, :amount)
            """
        ),
        {
            "id": repayment_id,
            "owner_id": user.id,
            "plan_id": plan_id,
            "posted_on": posted_on,
            "amount": amount,
        },
    )
    monthly = _monthly(plan["principal"], plan["parts"], money(repaid) + money(amount), count + 1)
    await request.state.db.execute(
        text("UPDATE instalment_plans SET monthly_amount = :monthly WHERE id = :id"),
        {"monthly": monthly, "id": plan_id},
    )
    fresh = await _plan(request, plan_id)
    return {"id": str(repayment_id), "plan": fresh}


@router.get("/obligations")
async def obligations(request: Request) -> dict:
    await current_user(request)
    result = await request.state.db.execute(
        text(
            """
            SELECT id, description, category, principal, parts, monthly_amount, posted_on
            FROM instalment_plans
            ORDER BY posted_on, id
            """
        )
    )
    plans = []
    commitment = money(0)
    for row in result.mappings():
        item = await _plan_dict(request, row)
        plans.append(item)
        if money(item["remaining"]) > 0:
            commitment += money(item["monthly_amount"])
    return {"plans": plans, "monthly_commitment": money_str(commitment)}


@router.post("/lifecycle/backups", status_code=201)
async def create_backup(body: BackupBody, request: Request) -> dict:
    user, _session = await current_user(request)
    payload = await export_payload(request.state.db, include_secrets=body.include_secrets)
    blob = seal_backup(payload, body.passphrase)
    backup_id = uuid.uuid4()
    await request.state.db.execute(
        text("INSERT INTO backups (id, owner_id, ciphertext) VALUES (:id, :owner_id, :ciphertext)"),
        {"id": backup_id, "owner_id": user.id, "ciphertext": blob},
    )
    await _record(request.state.db, user.id, "backup_created")
    return {"id": str(backup_id)}


@router.get("/lifecycle/backups/{backup_id}")
async def download_backup(backup_id: uuid.UUID, request: Request) -> Response:
    await current_user(request)
    blob = await request.state.db.scalar(
        text("SELECT ciphertext FROM backups WHERE id = :id"),
        {"id": backup_id},
    )
    if blob is None:
        raise ApiError(404, "not_found", "That backup does not exist.")
    return Response(
        content=bytes(blob),
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="spendpilot-backup-{backup_id}.bin"'},
    )


@router.post("/lifecycle/restore")
async def restore_backup(
    request: Request,
    passphrase: str = Form(),
    file: UploadFile = File(),
) -> dict:
    user, _session = await current_user(request)
    if len(passphrase) < 8 or len(passphrase) > 128:
        raise ApiError(422, "invalid_request", "Enter the backup passphrase.")
    raw = await file.read(16 * 1024 * 1024)
    if not raw:
        raise ApiError(422, "invalid_request", "Choose a backup file.")
    try:
        payload = open_backup(raw, passphrase)
    except BackupError as exc:
        raise ApiError(400, "backup_unreadable", "This backup could not be read. Existing data was left unchanged.") from exc
    try:
        async with request.state.db.begin_nested():
            await restore_payload(request.state.db, user.id, payload)
            await _record(request.state.db, user.id, "backup_restored")
    except BackupError as exc:
        raise ApiError(400, "backup_unreadable", "This backup could not be read. Existing data was left unchanged.") from exc
    return {"restored": True}


@router.post("/lifecycle/purge")
async def run_purge(request: Request) -> dict:
    user, _session = await current_user(request)
    await purge_expired(request.state.db)
    await _record(request.state.db, user.id, "purge_completed")
    return {"purged": True}


@router.get("/events")
async def events(request: Request) -> StreamingResponse:
    await current_user(request)
    header = request.headers.get("last-event-id") or "0"
    try:
        last_id = int(header)
    except ValueError:
        last_id = 0
    result = await request.state.db.execute(
        text("SELECT id, body FROM user_events WHERE id > :last_id ORDER BY id"),
        {"last_id": last_id},
    )
    rows = list(result.mappings())

    def stream():
        yield "retry: 15000\n: heartbeat\n\n"
        for row in rows:
            body = str(row["body"]).replace("\n", " ")
            yield f"id: {row['id']}\ndata: {body}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")


async def _load_plan(request: Request, plan_id: uuid.UUID):
    row = (
        await request.state.db.execute(
            text(
                """
                SELECT id, description, category, principal, parts, monthly_amount, posted_on
                FROM instalment_plans
                WHERE id = :id
                """
            ),
            {"id": plan_id},
        )
    ).mappings().first()
    if row is None:
        raise ApiError(404, "not_found", "That instalment does not exist.")
    return row


async def _repaid(request: Request, plan_id: uuid.UUID) -> tuple:
    row = (
        await request.state.db.execute(
            text(
                """
                SELECT COALESCE(SUM(amount), 0) AS repaid, count(*) AS repayment_count
                FROM instalment_repayments
                WHERE plan_id = :id
                """
            ),
            {"id": plan_id},
        )
    ).mappings().one()
    return row["repaid"], int(row["repayment_count"])


async def _plan(request: Request, plan_id: uuid.UUID) -> dict:
    return await _plan_dict(request, await _load_plan(request, plan_id))


async def _plan_dict(request: Request, row) -> dict:
    repaid, count = await _repaid(request, row["id"])
    remaining = money(row["principal"]) - money(repaid)
    repayments = (
        await request.state.db.execute(
            text(
                """
                SELECT id, posted_on, amount
                FROM instalment_repayments
                WHERE plan_id = :id
                ORDER BY posted_on, id
                """
            ),
            {"id": row["id"]},
        )
    ).mappings()
    return {
        "id": str(row["id"]),
        "description": row["description"],
        "category": row["category"],
        "principal": money_str(row["principal"]),
        "parts": row["parts"],
        "monthly_amount": money_str(row["monthly_amount"]),
        "posted_on": row["posted_on"].isoformat() if isinstance(row["posted_on"], date) else str(row["posted_on"]),
        "repaid": money_str(repaid),
        "remaining": money_str(remaining),
        "repayment_count": count,
        "repayments": [
            {"id": str(item["id"]), "posted_on": item["posted_on"].isoformat(), "amount": money_str(item["amount"])}
            for item in repayments
        ],
    }
