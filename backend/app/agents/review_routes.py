"""Monthly briefing, memories, and category corrections."""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Header, Request
from pydantic import BaseModel, Field
from sqlalchemy import text

from app.core.config import get_settings
from app.core.errors import ApiError
from app.identity.routes import current_user
from app.jobs.queue import defer_review
from app.lifecycle.routes import category_allowed

router = APIRouter(prefix="/api/v1", tags=["advisor"])
logger = logging.getLogger("spendpilot.reviews")


class ReviewBody(BaseModel):
    question: str | None = None


class MemoryBody(BaseModel):
    body: str = Field(min_length=1, max_length=500)


class CorrectionBody(BaseModel):
    transaction_id: uuid.UUID
    category: str


def defer_review_quietly(review_id: str, owner_id: str) -> None:
    try:
        defer_review(review_id, owner_id)
    except Exception:
        logger.exception("review_defer_failed", extra={"review_id": review_id})


@router.post("/reviews", status_code=202)
async def create_review(
    body: ReviewBody,
    request: Request,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict:
    user, _session = await current_user(request)
    await _require_consent(request)
    key = (idempotency_key or "").strip()[:200] or None
    if key:
        existing = await request.state.db.scalar(
            text("SELECT id FROM reviews WHERE idempotency_key = :key"),
            {"key": key},
        )
        if existing is not None:
            return await _payload(request.state.db, existing)
    review_id = uuid.uuid4()
    await request.state.db.execute(
        text(
            """
            INSERT INTO reviews (id, owner_id, idempotency_key, status, provider_mode, deadline_at)
            VALUES (:id, :owner_id, :key, 'queued', :mode, now() + interval '10 minutes')
            """
        ),
        {"id": review_id, "owner_id": user.id, "key": key, "mode": get_settings().provider_mode},
    )
    request.state.pending_reviews = [(str(review_id), str(user.id))]
    return await _payload(request.state.db, review_id)


@router.get("/reviews")
async def list_reviews(request: Request) -> dict:
    await current_user(request)
    result = await request.state.db.execute(
        text(
            """
            SELECT id FROM reviews
            WHERE status = 'published'
            ORDER BY created_at DESC
            LIMIT 12
            """
        )
    )
    return {"reviews": [await _payload(request.state.db, row["id"]) for row in result.mappings()]}


@router.get("/reviews/{review_id}")
async def read_review(review_id: uuid.UUID, request: Request) -> dict:
    await current_user(request)
    found = await request.state.db.scalar(text("SELECT id FROM reviews WHERE id = :id"), {"id": review_id})
    if found is None:
        raise ApiError(404, "not_found", "That review does not exist.")
    return await _payload(request.state.db, review_id)


@router.post("/reviews/{review_id}/cancel")
async def cancel_review(review_id: uuid.UUID, request: Request) -> dict:
    await current_user(request)
    await _transition(request, review_id, {"queued", "running", "paused"}, "cancelled")
    return await _payload(request.state.db, review_id)


@router.post("/reviews/{review_id}/pause")
async def pause_review(review_id: uuid.UUID, request: Request) -> dict:
    await current_user(request)
    await _transition(request, review_id, {"queued", "running"}, "paused")
    return await _payload(request.state.db, review_id)


@router.post("/reviews/{review_id}/resume")
async def resume_review(review_id: uuid.UUID, request: Request) -> dict:
    user, _session = await current_user(request)
    await _require_consent(request)
    await _transition(request, review_id, {"paused", "cancelled"}, "running")
    request.state.pending_reviews = [(str(review_id), str(user.id))]
    return await _payload(request.state.db, review_id)


@router.get("/memories")
async def list_memories(request: Request) -> dict:
    await current_user(request)
    result = await request.state.db.execute(
        text("SELECT id, kind, body, created_at FROM memories ORDER BY created_at")
    )
    return {
        "memories": [
            {
                "id": str(row["id"]),
                "kind": row["kind"],
                "body": row["body"],
                "created_at": row["created_at"].isoformat(),
            }
            for row in result.mappings()
        ]
    }


@router.post("/memories", status_code=201)
async def create_memory(body: MemoryBody, request: Request) -> dict:
    user, _session = await current_user(request)
    memory_id = uuid.uuid4()
    await request.state.db.execute(
        text(
            """
            INSERT INTO memories (id, owner_id, kind, body)
            VALUES (:id, :owner_id, 'confirmed_preference', :body)
            """
        ),
        {"id": memory_id, "owner_id": user.id, "body": body.body.strip()},
    )
    return {"id": str(memory_id), "kind": "confirmed_preference", "body": body.body.strip()}


@router.delete("/memories/{memory_id}")
async def delete_memory(memory_id: uuid.UUID, request: Request) -> dict:
    await current_user(request)
    deleted = await request.state.db.execute(
        text("DELETE FROM memories WHERE id = :id RETURNING id"),
        {"id": memory_id},
    )
    if deleted.first() is None:
        raise ApiError(404, "not_found", "That memory does not exist.")
    return {"deleted": True}


@router.post("/corrections", status_code=201)
async def stage_correction(body: CorrectionBody, request: Request) -> dict:
    user, _session = await current_user(request)
    if not await category_allowed(request.state.db, body.category):
        raise ApiError(422, "invalid_request", "Choose a category from the v1 list or one you added.")
    current = (
        await request.state.db.execute(
            text("SELECT id, category, description FROM posted_transactions WHERE id = :id"),
            {"id": body.transaction_id},
        )
    ).mappings().first()
    if current is None:
        raise ApiError(404, "not_found", "That transaction does not exist.")
    if current["category"] == body.category:
        raise ApiError(422, "invalid_request", "Choose a different category.")
    correction_id = uuid.uuid4()
    await request.state.db.execute(
        text(
            """
            INSERT INTO category_corrections (
                id, owner_id, transaction_id, original_category, proposed_category, status
            ) VALUES (:id, :owner_id, :transaction_id, :original, :proposed, 'staged')
            """
        ),
        {
            "id": correction_id,
            "owner_id": user.id,
            "transaction_id": body.transaction_id,
            "original": current["category"],
            "proposed": body.category,
        },
    )
    return {
        "id": str(correction_id),
        "transaction_id": str(body.transaction_id),
        "original_category": current["category"],
        "proposed_category": body.category,
        "description": current["description"],
        "status": "staged",
    }


@router.post("/corrections/{correction_id}/accept")
async def accept_correction(correction_id: uuid.UUID, request: Request) -> dict:
    user, _session = await current_user(request)
    row = (
        await request.state.db.execute(
            text(
                """
                SELECT id, transaction_id, original_category, proposed_category, status
                FROM category_corrections
                WHERE id = :id
                """
            ),
            {"id": correction_id},
        )
    ).mappings().first()
    if row is None:
        raise ApiError(404, "not_found", "That correction does not exist.")
    if row["status"] != "accepted":
        await request.state.db.execute(
            text("UPDATE posted_transactions SET category = :category WHERE id = :id"),
            {"category": row["proposed_category"], "id": row["transaction_id"]},
        )
        await request.state.db.execute(
            text(
                """
                UPDATE category_corrections
                SET status = 'accepted', accepted_at = now()
                WHERE id = :id AND status = 'staged'
                """
            ),
            {"id": correction_id},
        )
        marker = f'["{row["transaction_id"]}"]'
        await request.state.db.execute(
            text("UPDATE findings SET stale = true WHERE evidence_ids @> CAST(:marker AS jsonb)"),
            {"marker": marker},
        )
        await request.state.db.execute(
            text(
                """
                UPDATE briefings SET stale = true
                WHERE review_id IN (
                    SELECT review_id FROM findings
                    WHERE review_id IS NOT NULL AND evidence_ids @> CAST(:marker AS jsonb)
                )
                """
            ),
            {"marker": marker},
        )
        await request.state.db.execute(
            text("UPDATE scenarios SET stale = true WHERE category = :category"),
            {"category": row["original_category"]},
        )
        description = await request.state.db.scalar(
            text("SELECT description FROM posted_transactions WHERE id = :id"),
            {"id": row["transaction_id"]},
        )
        if description:
            await request.state.db.execute(
                text(
                    """
                    INSERT INTO category_rules (id, owner_id, description, category)
                    VALUES (:id, :owner_id, :description, :category)
                    ON CONFLICT (owner_id, description)
                    DO UPDATE SET category = EXCLUDED.category
                    """
                ),
                {
                    "id": uuid.uuid4(),
                    "owner_id": user.id,
                    "description": description,
                    "category": row["proposed_category"],
                },
            )
    return {
        "id": str(row["id"]),
        "transaction_id": str(row["transaction_id"]),
        "original_category": row["original_category"],
        "proposed_category": row["proposed_category"],
        "status": "accepted",
    }


async def _require_consent(request: Request) -> None:
    profile = (
        await request.state.db.execute(
            text("SELECT consent, document_assistance FROM provider_profiles")
        )
    ).mappings().first()
    if profile is None:
        raise ApiError(409, "provider_required", "Save a provider and a consent level first.")
    if profile["consent"] == "none":
        raise ApiError(403, "no_consent", "SpendPilot will not send ledger details while consent is off.")
    if profile["consent"] != "selected_transactions" or profile["document_assistance"]:
        raise ApiError(
            409,
            "consent_scope",
            "A monthly review needs consent for selected transaction details. Document assistance stays off.",
        )


async def _transition(request: Request, review_id, allowed: set[str], status: str) -> None:
    row = (
        await request.state.db.execute(
            text("SELECT status FROM reviews WHERE id = :id"),
            {"id": review_id},
        )
    ).mappings().first()
    if row is None:
        raise ApiError(404, "not_found", "That review does not exist.")
    if row["status"] not in allowed:
        raise ApiError(409, "review_state", "That review cannot change from its current state.")
    await request.state.db.execute(
        text("UPDATE reviews SET status = :status WHERE id = :id"),
        {"status": status, "id": review_id},
    )


async def _payload(db, review_id) -> dict:
    row = (
        await db.execute(
            text(
                """
                SELECT reviews.id, reviews.status, reviews.provider_mode, reviews.step, reviews.failure_code,
                       reviews.failure_message, reviews.activity, reviews.state, reviews.duplicate_of,
                       reviews.call_count, briefings.id AS briefing_id, briefings.title, briefings.explanation,
                       briefings.stale, scenarios.category, scenarios.baseline, scenarios.reduction,
                       scenarios.proposed, scenarios.income_total, scenarios.affordability_amount,
                       scenarios.affordability_blocked, scenarios.stale AS scenario_stale,
                       targets.id AS target_id, targets.status AS target_status
                FROM reviews
                LEFT JOIN briefings ON briefings.review_id = COALESCE(reviews.duplicate_of, reviews.id)
                LEFT JOIN scenarios ON scenarios.review_id = COALESCE(reviews.duplicate_of, reviews.id)
                LEFT JOIN targets ON targets.review_id = COALESCE(reviews.duplicate_of, reviews.id)
                WHERE reviews.id = :id
                """
            ),
            {"id": review_id},
        )
    ).mappings().one()
    state = row["state"] or {}
    scenario = None
    if row["category"] is not None:
        scenario = {
            "category": row["category"],
            "baseline": row["baseline"],
            "reduction": row["reduction"],
            "proposed": row["proposed"],
            "calculation_id": "category_reduction",
            "income_total": row["income_total"],
            "affordability_amount": row["affordability_amount"],
            "affordability_blocked": row["affordability_blocked"],
            "stale": row["scenario_stale"],
        }
    target = None
    if row["target_id"] is not None:
        target = {"id": str(row["target_id"]), "status": row["target_status"]}
    briefing = None
    if row["briefing_id"] is not None:
        briefing = {
            "id": str(row["briefing_id"]),
            "title": row["title"],
            "explanation": row["explanation"],
            "stale": row["stale"],
        }
    return {
        "id": str(row["id"]),
        "status": row["status"],
        "provider_mode": row["provider_mode"],
        "live": bool(state.get("live")),
        "step": row["step"],
        "call_count": row["call_count"],
        "specialists": state.get("specialists") or [],
        "memories": state.get("memories") or [],
        "activity": row["activity"] or [],
        "failure_code": row["failure_code"],
        "failure_message": row["failure_message"],
        "duplicate_of": str(row["duplicate_of"]) if row["duplicate_of"] else None,
        "briefing": briefing,
        "scenario": scenario,
        "target": target,
    }
