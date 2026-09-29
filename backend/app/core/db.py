from __future__ import annotations

from collections.abc import AsyncIterator
from uuid import UUID

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import Settings

OWNER_GUC = "app.owner_id"
LOGIN_GUC = "app.login_name"
SESSION_GUC = "app.session_token_hash"
TOKEN_GUC = "app.token_hash"
ACTOR_GUC = "app.actor_role"
SESSION_GUCS = (OWNER_GUC, LOGIN_GUC, SESSION_GUC, TOKEN_GUC, ACTOR_GUC)


class Base(DeclarativeBase):
    pass


def create_engine(settings: Settings, *, pool_size: int = 5, max_overflow: int = 5):
    engine = create_async_engine(
        settings.database_url_app,
        pool_pre_ping=True,
        pool_size=pool_size,
        max_overflow=max_overflow,
    )

    @event.listens_for(engine.sync_engine, "checkin")
    def _clear_owner_context(dbapi_connection, connection_record) -> None:
        if dbapi_connection is None:
            return
        cursor = dbapi_connection.cursor()
        try:
            for name in SESSION_GUCS:
                cursor.execute("SELECT set_config(%s, '', false)", (name,))
            dbapi_connection.commit()
        finally:
            cursor.close()

    return engine


def create_session_factory(settings: Settings) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(create_engine(settings), expire_on_commit=False)


async def set_config(session: AsyncSession, name: str, value: str) -> None:
    await session.execute(
        text("SELECT set_config(:name, :value, true)"),
        {"name": name, "value": value},
    )


async def set_owner(session: AsyncSession, owner_id: UUID) -> None:
    await set_config(session, OWNER_GUC, str(owner_id))


async def session_scope(
    factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
