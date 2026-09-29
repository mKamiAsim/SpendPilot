"""Cards and the shared account they belong to. A card does not store the account balance."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.core.config import get_settings
from app.core.crypto import parse_key_ring
from app.core.errors import ApiError
from app.identity.routes import current_user

router = APIRouter(prefix="/api/v1", tags=["cards"])

ACTIVE_LIMIT = 10


class CardBody(BaseModel):
    alias: str = Field(min_length=1, max_length=80)
    last4: str = Field(pattern=r"^[0-9]{4}$")
    account_alias: str = Field(min_length=1, max_length=80)
    account_last4: str = Field(pattern=r"^[0-9]{4}$")
    password: str | None = Field(default=None, max_length=128)


class CloseBody(BaseModel):
    status: str


def _card_dict(row) -> dict:
    return {
        "id": str(row["id"]),
        "alias": row["alias"],
        "last4": row["last4"],
        "status": row["status"],
        "password_saved": bool(row["password_saved"]),
        "account": {
            "id": str(row["account_id"]),
            "alias": row["account_alias"],
            "last4": row["account_last4"],
        },
    }


async def _load_card(db, card_id: uuid.UUID):
    result = await db.execute(
        text(
            """
            SELECT cards.id, cards.alias, cards.last4, cards.status,
                   cards.password_ciphertext IS NOT NULL AS password_saved,
                   card_accounts.id AS account_id,
                   card_accounts.alias AS account_alias,
                   card_accounts.last4 AS account_last4
            FROM cards
            JOIN card_accounts ON card_accounts.id = cards.account_id
            WHERE cards.id = :id
            """
        ),
        {"id": card_id},
    )
    return result.mappings().first()


@router.get("/cards")
async def list_cards(request: Request) -> dict:
    await current_user(request)
    result = await request.state.db.execute(
        text(
            """
            SELECT cards.id, cards.alias, cards.last4, cards.status,
                   cards.password_ciphertext IS NOT NULL AS password_saved,
                   card_accounts.id AS account_id,
                   card_accounts.alias AS account_alias,
                   card_accounts.last4 AS account_last4
            FROM cards
            JOIN card_accounts ON card_accounts.id = cards.account_id
            ORDER BY cards.created_at, cards.last4
            """
        )
    )
    return {"cards": [_card_dict(row) for row in result.mappings()]}


@router.post("/cards", status_code=201)
async def create_card(body: CardBody, request: Request) -> dict:
    user, _session = await current_user(request)
    db = request.state.db
    password = body.password.strip() if body.password else ""
    ciphertext = None
    if password:
        settings = get_settings()
        if not settings.encryption_keys or not settings.encryption_key_id:
            raise ApiError(
                503,
                "encryption_unconfigured",
                "A PDF password cannot be saved until an encryption key is configured.",
            )
        ciphertext = parse_key_ring(settings.encryption_keys, settings.encryption_key_id).encrypt(
            password.encode("utf-8")
        )
    await db.execute(
        text("SELECT pg_advisory_xact_lock(hashtext(current_setting('app.owner_id', true))::bigint)")
    )
    active = await db.scalar(text("SELECT count(*) FROM cards WHERE status = 'active'"))
    if active is not None and int(active) >= ACTIVE_LIMIT:
        raise ApiError(409, "card_limit", "Ten active cards is the limit. Close one before adding another.")
    account_id = await db.scalar(
        text("SELECT id FROM card_accounts WHERE last4 = :last4"),
        {"last4": body.account_last4},
    )
    if account_id is None:
        account_id = uuid.uuid4()
        await db.execute(
            text(
                """
                INSERT INTO card_accounts (id, owner_id, alias, last4)
                VALUES (:id, :owner_id, :alias, :last4)
                """
            ),
            {
                "id": account_id,
                "owner_id": user.id,
                "alias": body.account_alias.strip(),
                "last4": body.account_last4,
            },
        )
    card_id = uuid.uuid4()
    try:
        async with db.begin_nested():
            await db.execute(
                text(
                    """
                    INSERT INTO cards (id, owner_id, account_id, alias, last4, status, password_ciphertext)
                    VALUES (:id, :owner_id, :account_id, :alias, :last4, 'active', :password)
                    """
                ),
                {
                    "id": card_id,
                    "owner_id": user.id,
                    "account_id": account_id,
                    "alias": body.alias.strip(),
                    "last4": body.last4,
                    "password": ciphertext,
                },
            )
    except IntegrityError as exc:
        raise ApiError(409, "card_exists", "A card with those digits is already on this account.") from exc
    row = await _load_card(db, card_id)
    return _card_dict(row)


@router.patch("/cards/{card_id}")
async def close_card(card_id: uuid.UUID, body: CloseBody, request: Request) -> dict:
    await current_user(request)
    if body.status != "closed":
        raise ApiError(422, "invalid_request", "A card can be closed from this screen.")
    updated = await request.state.db.scalar(
        text("UPDATE cards SET status = 'closed' WHERE id = :id AND status = 'active' RETURNING id"),
        {"id": card_id},
    )
    if updated is None:
        raise ApiError(404, "not_found", "That card is not active.")
    row = await _load_card(request.state.db, card_id)
    return _card_dict(row)
