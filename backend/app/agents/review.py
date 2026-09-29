"""Monthly review. A replay publishes the same briefing and does not accept a second target."""

from __future__ import annotations

import hashlib
import json
import uuid

import psycopg
from psycopg.errors import UniqueViolation
from psycopg.rows import dict_row
from psycopg.types.json import Json

from app.agents.claims import validate_claims
from app.agents.finding import FindingRejected
from app.agents.limits import Budget
from app.agents.snapshot import freeze_snapshot
from app.agents.specialists import plan_roles, run_wave
from app.core.config import get_settings
from app.core.ssrf import SsrfError, SsrfPolicy, validate_endpoint
from app.jobs.queue import conninfo


def process_review(review_id: str, owner_id: str, *, max_steps: int | None = None) -> None:
    settings = get_settings()
    taken = 0
    with psycopg.connect(conninfo(settings.database_url_app), row_factory=dict_row) as conn:
        while True:
            if max_steps is not None and taken >= max_steps:
                return
            with conn.transaction():
                conn.execute("SELECT set_config('app.owner_id', %s, true)", (owner_id,))
                progressed = _one_step(conn, review_id, owner_id)
            if not progressed:
                return
            taken += 1


def prepare_provider(mode: str, profile) -> bool:
    """Fake mode does not open a socket. A blocked endpoint fails before any specialist runs."""

    if mode == "fake":
        return False
    if mode != "configured":
        raise FindingRejected("provider_failed", "The provider mode is not configured.")
    settings = get_settings()
    policy = SsrfPolicy(settings.private_model_hosts)
    validate_endpoint(profile["endpoint"], policy)
    from app.agents.openai_client import probe_endpoint
    from app.core.crypto import parse_key_ring

    api_key = None
    ciphertext = profile.get("api_key_ciphertext") if isinstance(profile, dict) else profile["api_key_ciphertext"]
    if ciphertext:
        ring = parse_key_ring(settings.encryption_keys, settings.encryption_key_id)
        api_key = ring.decrypt(ciphertext).decode("utf-8")

    def send(url: str, key: str | None, body: dict):
        import httpx

        headers = {"Content-Type": "application/json"}
        if key:
            headers["Authorization"] = f"Bearer {key}"
        with httpx.Client(timeout=10, follow_redirects=False) as client:
            return client.post(url, headers=headers, json=body)

    probed = probe_endpoint(profile["endpoint"], api_key, profile["model_name"], policy, send)
    if not probed.ok:
        if probed.code == "ssrf":
            raise SsrfError(probed.message)
        raise FindingRejected("provider_failed", probed.message)
    return True


def delegate_wave(mode: str, profile, snapshot: dict) -> dict:
    prepare_provider(mode, profile)
    budget = Budget()
    wave = run_wave(plan_roles("monthly"), snapshot, budget, depth=1)
    wave["call_count"] = budget.calls
    wave["live"] = mode == "configured"
    return wave


def _one_step(conn, review_id: str, owner_id: str) -> bool:
    row = conn.execute(
        "SELECT * FROM reviews WHERE id = %s FOR UPDATE",
        (review_id,),
    ).fetchone()
    if row is None or row["status"] in {"published", "failed", "cancelled", "linked", "paused"}:
        return False
    clock = conn.execute("SELECT now() AS now").fetchone()["now"]
    if row["deadline_at"] <= clock:
        _fail(conn, review_id, "deadline", "This review passed the 10-minute deadline.")
        return False
    profile = conn.execute(
        """
        SELECT endpoint, model_name, api_key_ciphertext, consent, consent_version, document_assistance
        FROM provider_profiles
        """
    ).fetchone()
    if profile is None or profile["consent"] != "selected_transactions" or profile["document_assistance"]:
        _fail(conn, review_id, "consent_scope", "Selected transaction details are required. Document assistance stays off.")
        return False
    step = row["step"]
    state = dict(row["state"] or {})
    if step == "authorise":
        state["activity"] = ["Checked consent and the 10-minute deadline."]
        _save(conn, review_id, owner_id, "snapshot", state, profile["consent_version"])
        return True
    if step == "snapshot":
        if row["snapshot_id"] is None:
            snapshot_id, body = freeze_snapshot(
                conn,
                consent=profile["consent"],
                consent_version=profile["consent_version"],
            )
            digest = _hash(body)
            conn.execute(
                "UPDATE reviews SET snapshot_id = %s, snapshot_hash = %s WHERE id = %s",
                (snapshot_id, digest, review_id),
            )
        state["activity"] = [*state.get("activity", []), "Froze the snapshot."]
        _save(conn, review_id, owner_id, "coverage", state, profile["consent_version"])
        return True
    if step == "coverage":
        body = _body(conn, row["snapshot_id"])
        blocked = body["totals"]["income_total"] == "0.00"
        state["income_blocked"] = blocked
        state["activity"] = [*state.get("activity", []), "Checked income coverage."]
        _save(conn, review_id, owner_id, "memories", state, profile["consent_version"])
        return True
    if step == "memories":
        memories = [
            item["body"]
            for item in conn.execute(
                """
                SELECT body FROM memories
                WHERE kind = 'confirmed_preference'
                ORDER BY created_at
                """
            ).fetchall()
        ]
        state["memories"] = memories
        state["activity"] = [*state.get("activity", []), f"Read {len(memories)} confirmed preferences."]
        _save(conn, review_id, owner_id, "delegate", state, profile["consent_version"])
        return True
    if step == "delegate":
        try:
            body = _body(conn, row["snapshot_id"])
            wave = delegate_wave(row["provider_mode"], profile, body)
            state["live"] = wave["live"]
            state["specialists"] = wave["specialists"]
            state["scenario"] = wave["scenario"]
            state["claims"] = wave["claims"]
            state["activity"] = [*state.get("activity", []), "Delegated to behaviour and scenario."]
            conn.execute("UPDATE reviews SET call_count = %s WHERE id = %s", (wave["call_count"], review_id))
        except (FindingRejected, SsrfError) as exc:
            code = exc.code if isinstance(exc, FindingRejected) else "ssrf"
            message = exc.message if isinstance(exc, FindingRejected) else str(exc)
            _fail(conn, review_id, code, message)
            return False
        _save(conn, review_id, owner_id, "validate", state, profile["consent_version"])
        return True
    if step == "validate":
        body = _body(conn, row["snapshot_id"])
        try:
            validate_claims(body, state.get("claims") or [], state.get("scenario"))
        except FindingRejected as exc:
            _fail(conn, review_id, exc.code, exc.message)
            return False
        state["activity"] = [*state.get("activity", []), "Checked each amount against its calculation id."]
        _save(conn, review_id, owner_id, "publish", state, profile["consent_version"])
        return True
    if step == "publish":
        _publish(conn, row, owner_id, state)
        return False
    _fail(conn, review_id, "provider_failed", "The review step was not recognised.")
    return False


def _publish(conn, row, owner_id: str, state: dict) -> None:
    existing = conn.execute(
        """
        SELECT id FROM reviews
        WHERE snapshot_hash = %s AND status = 'published' AND id <> %s
        FOR UPDATE
        """,
        (row["snapshot_hash"], row["id"]),
    ).fetchone()
    if existing is not None:
        _link(conn, row["id"], existing["id"])
        return
    try:
        with conn.transaction():
            _insert_published(conn, row, owner_id, state)
    except UniqueViolation as exc:
        if getattr(exc.diag, "constraint_name", "") != "reviews_owner_hash_idx":
            raise
        winner = conn.execute(
            """
            SELECT id FROM reviews
            WHERE snapshot_hash = %s AND status = 'published' AND id <> %s
            """,
            (row["snapshot_hash"], row["id"]),
        ).fetchone()
        if winner is None:
            raise
        _link(conn, row["id"], winner["id"])


def _insert_published(conn, row, owner_id: str, state: dict) -> None:
    body = _body(conn, row["snapshot_id"])
    scenario = state.get("scenario")
    title, explanation = _copy(body, scenario, state.get("income_blocked", True))
    activity = [*state.get("activity", []), "Published one briefing."]
    briefing_id = uuid.uuid4()
    conn.execute(
        """
        INSERT INTO briefings (id, owner_id, review_id, snapshot_id, title, explanation)
        VALUES (%s, %s, %s, %s, %s, %s)
        """,
        (briefing_id, owner_id, row["id"], row["snapshot_id"], title, explanation),
    )
    spending = next(item for item in state["claims"] if item["calculation_id"] == "net_spending")
    conn.execute(
        """
        INSERT INTO findings (
            id, owner_id, review_id, snapshot_id, title, explanation, severity,
            evidence_ids, calculation_id, amount
        ) VALUES (%s, %s, %s, %s, %s, %s, 'note', %s, 'net_spending', %s)
        """,
        (
            uuid.uuid4(),
            owner_id,
            row["id"],
            row["snapshot_id"],
            title,
            explanation,
            Json(spending["evidence_ids"]),
            spending["amount"],
        ),
    )
    if scenario is not None:
        scenario_id = uuid.uuid4()
        conn.execute(
            """
            INSERT INTO scenarios (
                id, owner_id, review_id, snapshot_id, category, baseline, reduction, proposed,
                calculation_id, income_total, affordability_amount, affordability_blocked
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'category_reduction', %s, %s, %s)
            """,
            (
                scenario_id,
                owner_id,
                row["id"],
                row["snapshot_id"],
                scenario["category"],
                scenario["baseline"],
                scenario["reduction"],
                scenario["proposed"],
                scenario["income_total"],
                scenario["affordability_amount"],
                scenario["affordability_blocked"],
            ),
        )
        conn.execute(
            """
            INSERT INTO targets (
                id, owner_id, review_id, scenario_id, category, baseline, reduction, proposed,
                calculation_id, status
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'category_reduction', 'staged')
            """,
            (
                uuid.uuid4(),
                owner_id,
                row["id"],
                scenario_id,
                scenario["category"],
                scenario["baseline"],
                scenario["reduction"],
                scenario["proposed"],
            ),
        )
    conn.execute(
        """
        UPDATE reviews
        SET status = 'published', step = 'published', state = %s, activity = %s,
            failure_code = NULL, failure_message = NULL
        WHERE id = %s
        """,
        (Json(state), Json(activity), row["id"]),
    )


def _link(conn, review_id, canonical_id) -> None:
    conn.execute(
        """
        UPDATE reviews
        SET status = 'linked', duplicate_of = %s, step = 'published'
        WHERE id = %s
        """,
        (canonical_id, review_id),
    )


def _copy(body: dict, scenario: dict | None, income_blocked: bool) -> tuple[str, str]:
    net = body["totals"]["net_spending"]
    title = f"Posted net spending is {net} AED"
    parts = [
        "Posted net spending is purchases minus refunds, plus manual cash purchases.",
        "Payments, transfers, and cash withdrawals are not included.",
        f"The spending total is {net} AED.",
    ]
    if scenario is not None:
        parts.append(
            f"{scenario['category']} would be {scenario['proposed']} AED after a {scenario['reduction']} AED reduction."
        )
    if income_blocked:
        parts.append("Income is not in this snapshot, so this is not an affordability claim.")
    elif scenario is not None and scenario.get("affordability_amount"):
        parts.append(
            f"Leftover after the reduced net spending is {scenario['affordability_amount']} AED."
        )
    return title, " ".join(parts)


def _save(conn, review_id, owner_id, nxt: str, state: dict, consent_version: int) -> None:
    conn.execute(
        """
        INSERT INTO review_checkpoints (id, owner_id, review_id, step, state)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (review_id, step) DO UPDATE SET state = EXCLUDED.state, created_at = now()
        """,
        (uuid.uuid4(), owner_id, review_id, nxt, Json(state)),
    )
    conn.execute(
        """
        UPDATE reviews
        SET status = 'running', step = %s, state = %s, consent_version = %s, activity = %s
        WHERE id = %s
        """,
        (nxt, Json(state), consent_version, Json(state.get("activity") or []), review_id),
    )


def _fail(conn, review_id, code: str, message: str) -> None:
    conn.execute(
        """
        UPDATE reviews
        SET status = 'failed', failure_code = %s, failure_message = %s
        WHERE id = %s AND status IN ('queued', 'running')
        """,
        (code, message, review_id),
    )


def _body(conn, snapshot_id) -> dict:
    return conn.execute("SELECT body FROM snapshots WHERE id = %s", (snapshot_id,)).fetchone()["body"]


def _hash(body: dict) -> str:
    encoded = json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


