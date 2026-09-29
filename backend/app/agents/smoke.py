"""Live smoke test. An empty URL stays pending and does not open a connection."""

from __future__ import annotations

import httpx

from app.agents.openai_client import probe_endpoint
from app.core.config import get_settings
from app.core.ssrf import SsrfPolicy


def live_smoke_from_env() -> dict:
    settings = get_settings()
    url = settings.model_smoke_url.strip()
    if not url:
        return {
            "status": "pending",
            "live": False,
            "checked": False,
            "message": "MODEL_SMOKE_URL is not configured. Live tool-calling is unverified.",
        }
    policy = SsrfPolicy(settings.private_model_hosts)
    model = settings.model_smoke_model.strip() or "local"

    def send(target: str, api_key: str | None, body: dict) -> httpx.Response:
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        with httpx.Client(timeout=10, follow_redirects=False) as client:
            return client.post(target, headers=headers, json=body)

    result = probe_endpoint(url, settings.model_smoke_api_key or None, model, policy, send)
    return {
        "status": "ok" if result.ok else "failed",
        "live": True,
        "checked": True,
        "message": result.message,
    }
