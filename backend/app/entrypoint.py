from __future__ import annotations

import os
import sys
import time

import psycopg
from alembic import command
from alembic.config import Config

from app.core.config import get_settings
from app.jobs.queue import apply_queue_schema, conninfo


def wait_until_ready() -> None:
    settings = get_settings()
    last_error = "database was not ready"
    for _ in range(60):
        try:
            with psycopg.connect(conninfo(settings.database_url_app), connect_timeout=3) as connection:
                # The runtime role cannot read alembic_version. The queue table
                # exists only after the API has finished both migration steps.
                connection.execute("SELECT 1 FROM procrastinate_jobs LIMIT 1")
            return
        except Exception as exc:
            last_error = str(exc)
            print(last_error, file=sys.stderr)
            time.sleep(1)
    raise SystemExit(last_error)


def migrate() -> None:
    cfg = Config("alembic.ini")
    command.upgrade(cfg, "head")
    apply_queue_schema()


def main() -> None:
    process = os.environ.get("SPENDPILOT_PROCESS", "api")
    if process == "api":
        migrate()
        os.execvp(
            "uvicorn",
            ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"],
        )
    wait_until_ready()
    if process == "document-worker":
        from app.workers.document import main as run

        run()
        return
    if process == "agent-worker":
        from app.workers.agent import main as run

        run()
        return
    raise SystemExit(f"Unknown SPENDPILOT_PROCESS {process}")


if __name__ == "__main__":
    main()
