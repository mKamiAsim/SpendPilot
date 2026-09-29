from __future__ import annotations

import base64
import os
import socket
import subprocess
import tempfile
import time
import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine, text

ROOT = Path(__file__).resolve().parents[2]
INIT_SCRIPT = ROOT / "infra" / "docker" / "postgres" / "init-roles.sh"


def _docker() -> list[str]:
    try:
        subprocess.check_call(["docker", "info"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return ["docker"]
    except (OSError, subprocess.CalledProcessError):
        return ["sudo", "docker"]


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.fixture(scope="session")
def database_env() -> Iterator[dict[str, str]]:
    docker = _docker()
    name = f"spendpilot-test-{uuid.uuid4().hex[:8]}"
    port = _free_port()
    bootstrap = uuid.uuid4().hex
    migrator = uuid.uuid4().hex
    app_password = uuid.uuid4().hex
    subprocess.check_call(
        [
            *docker,
            "run",
            "-d",
            "--name",
            name,
            "-e",
            f"POSTGRES_PASSWORD={bootstrap}",
            "-e",
            "POSTGRES_USER=spendpilot_bootstrap",
            "-e",
            "POSTGRES_DB=spendpilot",
            "-e",
            f"SPENDPILOT_MIGRATOR_PASSWORD={migrator}",
            "-e",
            f"SPENDPILOT_APP_PASSWORD={app_password}",
            "-p",
            f"127.0.0.1:{port}:5432",
            "-v",
            f"{INIT_SCRIPT}:/docker-entrypoint-initdb.d/01-roles.sh:ro",
            "postgres:18.6",
        ]
    )
    migrator_url = f"postgresql+psycopg://spendpilot_migrator:{migrator}@127.0.0.1:{port}/spendpilot"
    app_url = f"postgresql+psycopg://spendpilot_app:{app_password}@127.0.0.1:{port}/spendpilot"
    try:
        deadline = time.time() + 90
        last_error = "postgres did not become ready"
        while time.time() < deadline:
            try:
                engine = create_engine(migrator_url)
                with engine.connect() as connection:
                    connection.execute(text("SELECT 1"))
                engine.dispose()
                break
            except Exception as exc:
                last_error = str(exc)
                time.sleep(1)
        else:
            logs = subprocess.check_output([*docker, "logs", name], text=True)
            raise RuntimeError(f"{last_error}\n{logs}")

        os.environ["DATABASE_URL_MIGRATOR"] = migrator_url
        os.environ["DATABASE_URL_APP"] = app_url
        os.environ["PUBLIC_APP_URL"] = "http://localhost:8080"
        os.environ["ALLOWED_ORIGINS"] = "http://localhost:8080,http://127.0.0.1:5173"
        os.environ["COOKIE_SECURE"] = "false"
        os.environ["EMAIL_DELIVERY"] = "capture"
        os.environ["SMTP_HOST"] = ""
        os.environ["IDLE_LOCK_MINUTES"] = "15"
        storage = tempfile.mkdtemp(prefix="spendpilot-files-")
        os.environ["FILE_STORAGE_DIR"] = storage
        os.environ["APP_ENCRYPTION_KEYS"] = "test:" + base64.b64encode(b"\x00" * 32).decode()
        os.environ["APP_ENCRYPTION_KEY_ID"] = "test"
        from app.core.config import get_settings
        from app.jobs.queue import apply_queue_schema

        get_settings.cache_clear()
        command.upgrade(Config(str(ROOT / "backend" / "alembic.ini")), "head")
        apply_queue_schema()
        yield {
            "migrator_url": migrator_url,
            "app_url": app_url,
            "container": name,
        }
    finally:
        subprocess.call([*docker, "rm", "-f", name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


@pytest.fixture(scope="session")
def application(database_env):
    from app.core.config import get_settings
    from app.main import create_app

    get_settings.cache_clear()
    return create_app()


@pytest.fixture
async def client(application) -> AsyncClient:
    transport = ASGITransport(app=application)
    async with AsyncClient(transport=transport, base_url="http://localhost:8080") as http:
        yield http


@pytest.fixture
def migrator(database_env):
    engine = create_engine(database_env["migrator_url"])
    yield engine
    engine.dispose()


async def csrf_headers(client: AsyncClient) -> dict[str, str]:
    response = await client.get("/api/v1/auth/csrf")
    assert response.status_code == 200, response.text
    return {"X-CSRF-Token": response.json()["csrf_token"]}


async def register(client: AsyncClient, username: str, email: str, password: str = "correct-horse-1") -> dict:
    response = await client.post(
        "/api/v1/auth/register",
        headers=await csrf_headers(client),
        json={"username": username, "email": email, "password": password},
    )
    assert response.status_code == 201, response.text
    return response.json()
