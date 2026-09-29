"""One investigation. A retry publishes the same finding and does not call another provider."""

from __future__ import annotations

import uuid

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Json

from app.agents.fake import fake_finding
from app.agents.finding import FindingDraft, FindingRejected, validate_finding
from app.agents.openai_client import investigate_live
from app.agents.snapshot import freeze_snapshot
from app.core.config import get_settings
from app.core.crypto import parse_key_ring
from app.core.ssrf import SsrfError, SsrfPolicy
from app.jobs.queue import conninfo


def process_investigation(investigation_id: str, owner_id: str) -> None:
    settings = get_settings()
    with psycopg.connect(conninfo(settings.database_url_app), row_factory=dict_row) as conn:
        with conn.transaction():
            conn.execute("SELECT set_config('app.owner_id', %s, true)", (owner_id,))
            row = conn.execute(
                """
                SELECT id, status, question, provider_mode, snapshot_id
                FROM investigations
                WHERE id = %s
                FOR UPDATE
                """,
                (investigation_id,),
            ).fetchone()
            if row is None or row["status"] != "queued":
                return
            profile = conn.execute(
                """
                SELECT endpoint, model_name, api_key_ciphertext, consent, consent_version
                FROM provider_profiles
                """
            ).fetchone()
            if profile is None or profile["consent"] != "selected_transactions":
                _fail(conn, investigation_id, "consent_scope", "Selected transaction details are required.")
                return
            if row["snapshot_id"] is None:
                snapshot_id, body = freeze_snapshot(
                    conn,
                    consent=profile["consent"],
                    consent_version=profile["consent_version"],
                )
                conn.execute(
                    "UPDATE investigations SET snapshot_id = %s WHERE id = %s",
                    (snapshot_id, investigation_id),
                )
            else:
                stored = conn.execute(
                    "SELECT body FROM snapshots WHERE id = %s",
                    (row["snapshot_id"],),
                ).fetchone()
                body = stored["body"]
                snapshot_id = str(row["snapshot_id"])
            try:
                draft, activity = _run_provider(row["provider_mode"], profile, body)
                validate_finding(body, draft)
            except FindingRejected as exc:
                _fail(conn, investigation_id, exc.code, exc.message)
                return
            except SsrfError as exc:
                _fail(conn, investigation_id, "ssrf", str(exc))
                return
            _publish(conn, investigation_id, owner_id, snapshot_id, draft, activity)


def _run_provider(mode: str, profile, snapshot: dict) -> tuple[FindingDraft, list[str]]:
    if mode == "fake":
        return fake_finding(snapshot)
    if mode != "configured":
        raise FindingRejected("provider_failed", "The provider mode is not configured.")
    settings = get_settings()
    api_key = None
    if profile["api_key_ciphertext"]:
        ring = parse_key_ring(settings.encryption_keys, settings.encryption_key_id)
        api_key = ring.decrypt(profile["api_key_ciphertext"]).decode("utf-8")
    policy = SsrfPolicy(settings.private_model_hosts)

    def send(url: str, key: str | None, body: dict):
        import httpx

        headers = {"Content-Type": "application/json"}
        if key:
            headers["Authorization"] = f"Bearer {key}"
        with httpx.Client(timeout=20, follow_redirects=False) as client:
            return client.post(url, headers=headers, json=body)

    return investigate_live(
        profile["endpoint"],
        api_key,
        profile["model_name"],
        snapshot,
        policy,
        send,
    )


def _publish(conn, investigation_id: str, owner_id: str, snapshot_id: str, draft: FindingDraft, activity: list[str]) -> None:
    existing = conn.execute(
        "SELECT id FROM findings WHERE investigation_id = %s",
        (investigation_id,),
    ).fetchone()
    if existing is None:
        conn.execute(
            """
            INSERT INTO findings (
                id, owner_id, investigation_id, snapshot_id, title, explanation,
                severity, evidence_ids, calculation_id, amount
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                uuid.uuid4(),
                owner_id,
                investigation_id,
                snapshot_id,
                draft.title,
                draft.explanation,
                draft.severity,
                Json(list(draft.evidence_ids)),
                draft.calculation_id,
                draft.amount,
            ),
        )
    conn.execute(
        """
        UPDATE investigations
        SET status = 'published', failure_code = NULL, failure_message = NULL, activity = %s
        WHERE id = %s
        """,
        (Json(activity), investigation_id),
    )


def _fail(conn, investigation_id: str, code: str, message: str) -> None:
    conn.execute(
        """
        UPDATE investigations
        SET status = 'failed', failure_code = %s, failure_message = %s
        WHERE id = %s AND status = 'queued'
        """,
        (code, message, investigation_id),
    )
