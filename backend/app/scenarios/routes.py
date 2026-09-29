"""A calculation is not an accepted target. The user accepts the target separately."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Header, Request
from pydantic import BaseModel, Field
from sqlalchemy import text

import psycopg
from psycopg.rows import dict_row

from app.core.config import get_settings
from app.core.errors import ApiError
from app.identity.routes import current_user
from app.jobs.queue import conninfo
from app.scenarios.calc import calculate_scenario
from app.agents.snapshot import read_snapshot_body

router = APIRouter(prefix="/api/v1", tags=["scenarios"])


class ScenarioBody(BaseModel):
    category: str
    reduction: str = Field(min_length=1, max_length=40)


@router.post("/scenarios", status_code=201)
async def create_scenario(body: ScenarioBody, request: Request) -> dict:
    user, _session = await current_user(request)
    try:
        stored = _store_scenario(str(user.id), body.category, body.reduction)
    except ValueError as exc:
        raise ApiError(422, "invalid_request", str(exc)) from exc
    return stored


@router.get("/scenarios")
async def list_scenarios(request: Request) -> dict:
    await current_user(request)
    result = await request.state.db.execute(
        text(
            """
            SELECT id, category, baseline, reduction, proposed, calculation_id, income_total,
                   affordability_amount, affordability_blocked, stale
            FROM scenarios
            ORDER BY created_at DESC
            LIMIT 20
            """
        )
    )
    return {"scenarios": [_scenario_dict(row) for row in result.mappings()]}


@router.post("/scenarios/{scenario_id}/target", status_code=201)
async def stage_target(
    scenario_id: uuid.UUID,
    request: Request,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict:
    user, _session = await current_user(request)
    scenario = (
        await request.state.db.execute(
            text(
                """
                SELECT id, category, baseline, reduction, proposed, calculation_id
                FROM scenarios
                WHERE id = :id
                """
            ),
            {"id": scenario_id},
        )
    ).mappings().first()
    if scenario is None:
        raise ApiError(404, "not_found", "That scenario does not exist.")
    key = (idempotency_key or "").strip()[:200] or None
    if key:
        existing = (
            await request.state.db.execute(
                text("SELECT id, status FROM targets WHERE idempotency_key = :key"),
                {"key": key},
            )
        ).mappings().first()
        if existing is not None:
            return {"id": str(existing["id"]), "status": existing["status"]}
    target_id = uuid.uuid4()
    await request.state.db.execute(
        text(
            """
            INSERT INTO targets (
                id, owner_id, scenario_id, category, baseline, reduction, proposed,
                calculation_id, status, idempotency_key
            ) VALUES (
                :id, :owner_id, :scenario_id, :category, :baseline, :reduction, :proposed,
                :calculation_id, 'staged', :key
            )
            """
        ),
        {
            "id": target_id,
            "owner_id": user.id,
            "scenario_id": scenario["id"],
            "category": scenario["category"],
            "baseline": scenario["baseline"],
            "reduction": scenario["reduction"],
            "proposed": scenario["proposed"],
            "calculation_id": scenario["calculation_id"],
            "key": key,
        },
    )
    return {"id": str(target_id), "status": "staged"}


@router.post("/targets/{target_id}/accept")
async def accept_target(target_id: uuid.UUID, request: Request) -> dict:
    await current_user(request)
    row = (
        await request.state.db.execute(
            text("SELECT id, status, category, reduction, proposed, calculation_id FROM targets WHERE id = :id"),
            {"id": target_id},
        )
    ).mappings().first()
    if row is None:
        raise ApiError(404, "not_found", "That target does not exist.")
    if row["status"] != "accepted":
        await request.state.db.execute(
            text(
                """
                UPDATE targets
                SET status = 'accepted', accepted_at = now()
                WHERE id = :id AND status = 'staged'
                """
            ),
            {"id": target_id},
        )
    return {
        "id": str(row["id"]),
        "status": "accepted",
        "category": row["category"],
        "reduction": row["reduction"],
        "proposed": row["proposed"],
        "calculation_id": row["calculation_id"],
    }


def _store_scenario(owner_id: str, category: str, reduction: str) -> dict:
    settings = get_settings()
    with psycopg.connect(conninfo(settings.database_url_app), row_factory=dict_row) as conn:
        with conn.transaction():
            conn.execute("SELECT set_config('app.owner_id', %s, true)", (owner_id,))
            body = read_snapshot_body(conn)
            calculated = calculate_scenario(body, {"category": category, "reduction": reduction, "user_id": "ignored"})
            scenario_id = uuid.uuid4()
            conn.execute(
                """
                INSERT INTO scenarios (
                    id, owner_id, category, baseline, reduction, proposed, calculation_id,
                    income_total, affordability_amount, affordability_blocked
                ) VALUES (%s, %s, %s, %s, %s, %s, 'category_reduction', %s, %s, %s)
                """,
                (
                    scenario_id,
                    owner_id,
                    calculated["category"],
                    calculated["baseline"],
                    calculated["reduction"],
                    calculated["proposed"],
                    calculated["income_total"],
                    calculated["affordability_amount"],
                    calculated["affordability_blocked"],
                ),
            )
    calculated["id"] = str(scenario_id)
    calculated.pop("evidence_ids", None)
    return calculated


def _scenario_dict(row) -> dict:
    return {
        "id": str(row["id"]),
        "category": row["category"],
        "baseline": row["baseline"],
        "reduction": row["reduction"],
        "proposed": row["proposed"],
        "calculation_id": row["calculation_id"],
        "income_total": row["income_total"],
        "affordability_amount": row["affordability_amount"],
        "affordability_blocked": row["affordability_blocked"],
        "stale": row["stale"],
    }
