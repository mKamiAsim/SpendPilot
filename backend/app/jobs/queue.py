from __future__ import annotations

import psycopg
from procrastinate import App, Blueprint, PsycopgConnector

from app.core.config import Settings, get_settings

tasks = Blueprint()


@tasks.task(name="documents.ready", queue="documents")
def documents_ready() -> str:
    """Queue registration for the document worker."""

    return "ok"


@tasks.task(name="documents.import_file", queue="documents", retry=5)
def import_document(document_id: str, owner_id: str) -> None:
    """Decrypt and post one file. A retry returns once the document is no longer queued."""

    from app.ingestion.process import process_document

    process_document(document_id, owner_id)


def defer_import(document_id: str, owner_id: str) -> None:
    app = get_queue_app()
    with app.open():
        import_document.defer(document_id=document_id, owner_id=owner_id)


@tasks.task(name="agents.ready", queue="agents")
def agents_ready() -> str:
    """Queue registration for the agent worker."""

    return "ok"


@tasks.task(name="agents.investigate", queue="agents", retry=3)
def investigate(investigation_id: str, owner_id: str) -> None:
    """Publish one finding. A retry returns once the investigation is no longer queued."""

    from app.agents.investigate import process_investigation

    process_investigation(investigation_id, owner_id)


def defer_investigation(investigation_id: str, owner_id: str) -> None:
    app = get_queue_app()
    with app.open():
        investigate.defer(investigation_id=investigation_id, owner_id=owner_id)


def conninfo(url: str) -> str:
    prefix = "postgresql+psycopg://"
    if url.startswith(prefix):
        return "postgresql://" + url.removeprefix(prefix)
    return url


_queue_app: App | None = None


def get_queue_app() -> App:
    global _queue_app
    if _queue_app is None:
        settings = get_settings()
        app = App(
            connector=PsycopgConnector(conninfo=conninfo(settings.database_url_app)),
            import_paths=["app.jobs.queue"],
        )
        app.add_tasks_from(tasks, namespace="spendpilot")
        _queue_app = app
    return _queue_app


def apply_queue_schema(settings: Settings | None = None) -> None:
    settings = settings or get_settings()
    migrator = conninfo(settings.database_url_migrator)
    with psycopg.connect(migrator) as connection:
        present = connection.execute("SELECT to_regclass('public.procrastinate_jobs')").fetchone()
        if present and present[0]:
            _grant_queue(connection)
            return
    app = App(connector=PsycopgConnector(conninfo=migrator))
    with app.open():
        app.schema_manager.apply_schema()
    with psycopg.connect(migrator) as connection:
        _grant_queue(connection)


def _grant_queue(connection: psycopg.Connection) -> None:
    connection.execute(
        """
        DO $$
        DECLARE
            table_name text;
            seq_name text;
        BEGIN
            FOR table_name IN
                SELECT tablename FROM pg_tables
                WHERE schemaname = 'public' AND tablename LIKE 'procrastinate%'
            LOOP
                EXECUTE format(
                    'GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.%I TO spendpilot_app',
                    table_name
                );
            END LOOP;
            FOR seq_name IN
                SELECT sequences.sequence_name
                FROM information_schema.sequences AS sequences
                WHERE sequences.sequence_schema = 'public'
                  AND sequences.sequence_name LIKE 'procrastinate%'
            LOOP
                EXECUTE format(
                    'GRANT USAGE, SELECT ON SEQUENCE public.%I TO spendpilot_app',
                    seq_name
                );
            END LOOP;
        END $$;
        """
    )
    connection.commit()
