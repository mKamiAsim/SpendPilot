"""Locked monthly harness and owner-scoped LangGraph checkpoints."""

from __future__ import annotations

import uuid

import psycopg
from langchain_core.messages import HumanMessage
from langgraph.graph import END, START, StateGraph
from psycopg.rows import dict_row
from sqlalchemy import text
from typing_extensions import TypedDict

from app.agents.harness import (
    FORBIDDEN_TOOLS,
    SpendPilotChat,
    build_monthly_agent,
    last_bound_tools,
    uses_deep_agent,
)
from app.agents.langgraph_store import CheckpointOwnerError, OwnerCheckpointSaver
from app.agents.limits import MAX_DELEGATION_DEPTH, MAX_MODEL_CALLS, MAX_PARALLEL_SPECIALISTS, REVIEW_DEADLINE, ReviewLimit
from app.agents.specialists import plan_roles
from app.core.config import get_settings
from app.jobs.queue import conninfo


class _State(TypedDict):
    note: str


def test_forbidden_tools_cannot_turn_on():
    assert uses_deep_agent("question") is False
    assert uses_deep_agent("monthly") is True
    assert plan_roles("question") == []
    assert plan_roles("monthly") == ["behaviour", "scenario"]
    assert MAX_MODEL_CALLS == 40
    assert MAX_DELEGATION_DEPTH == 2
    assert MAX_PARALLEL_SPECIALISTS == 2
    assert REVIEW_DEADLINE.total_seconds() == 600
    for name in ("execute", "shell", "python", "read_file", "write_file", "web_search", "web_fetch"):
        with_error = False
        try:
            build_monthly_agent(requested_tools=[name])
        except ReviewLimit as exc:
            with_error = exc.code == "tools"
        assert with_error, name
    try:
        build_monthly_agent(backend=object())
    except ReviewLimit as exc:
        assert exc.code == "tools"
    else:
        raise AssertionError("a host backend was accepted")
    model = SpendPilotChat()
    for name in FORBIDDEN_TOOLS:
        failed = False
        try:
            model.bind_tools([type("Tool", (), {"name": name})()])
        except ReviewLimit:
            failed = True
        assert failed, name
    agent = build_monthly_agent()
    agent.invoke({"messages": [HumanMessage(content="Monthly review of posted rows.")]})
    bound = last_bound_tools()
    assert bound == ["task"]
    assert FORBIDDEN_TOOLS.isdisjoint(bound)


def test_one_user_cannot_read_another_users_langgraph_checkpoint(database_env):
    from sqlalchemy import create_engine

    settings = get_settings()
    engine = create_engine(database_env["migrator_url"])
    owner = str(uuid.uuid4())
    other = str(uuid.uuid4())
    with engine.begin() as connection:
        for user_id, name in ((owner, "owner"), (other, "other")):
            connection.execute(
                text(
                    """
                    INSERT INTO users (id, username, email, password_hash, email_verified_at)
                    VALUES (:id, :username, :email, 'x', now())
                    """
                ),
                {"id": user_id, "username": f"{name}{user_id[:8]}", "email": f"{name}{user_id[:8]}@example.com"},
            )
    engine.dispose()

    note = f"checkpoint-secret-{uuid.uuid4().hex}"
    thread_id = str(uuid.uuid4())

    def graph(saver: OwnerCheckpointSaver):
        builder = StateGraph(_State)
        builder.add_node("keep", lambda state: {"note": state["note"]})
        builder.add_edge(START, "keep")
        builder.add_edge("keep", END)
        return builder.compile(checkpointer=saver)

    with psycopg.connect(conninfo(settings.database_url_app), row_factory=dict_row) as conn:
        with conn.transaction():
            conn.execute("SELECT set_config('app.owner_id', %s, true)", (owner,))
            saver = OwnerCheckpointSaver(conn)
            graph(saver).invoke(
                {"note": note},
                {"configurable": {"thread_id": thread_id, "owner_id": owner}},
            )
            stored = saver.get_tuple({"configurable": {"thread_id": thread_id, "owner_id": owner}})
            assert stored is not None
            assert stored.checkpoint["channel_values"]["note"] == note
            try:
                saver.get_tuple({"configurable": {"thread_id": thread_id, "owner_id": other}})
            except CheckpointOwnerError:
                pass
            else:
                raise AssertionError("another owner id was accepted on this session")

    with psycopg.connect(conninfo(settings.database_url_app), row_factory=dict_row) as conn:
        with conn.transaction():
            conn.execute("SELECT set_config('app.owner_id', %s, true)", (other,))
            hidden = OwnerCheckpointSaver(conn).get_tuple(
                {"configurable": {"thread_id": thread_id, "owner_id": other}}
            )
            assert hidden is None
            count = conn.execute("SELECT count(*) AS n FROM langgraph_checkpoints").fetchone()["n"]
            assert count == 0
            leaked = conn.execute(
                "SELECT checkpoint_blob FROM langgraph_checkpoints WHERE thread_id = %s",
                (thread_id,),
            ).fetchone()
            assert leaked is None
