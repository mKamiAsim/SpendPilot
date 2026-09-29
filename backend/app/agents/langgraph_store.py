"""LangGraph checkpoint saver. Rows carry an owner and row-level security."""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from typing import Any

import psycopg
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import (
    BaseCheckpointSaver,
    ChannelVersions,
    Checkpoint,
    CheckpointMetadata,
    CheckpointTuple,
    get_checkpoint_id,
)


class CheckpointOwnerError(Exception):
    pass


class OwnerCheckpointSaver(BaseCheckpointSaver):
    """Persist LangGraph checkpoints on the caller's connection.

    The connection must already have ``app.owner_id`` set. Another user's
    session cannot read or write these rows.
    """

    def __init__(self, conn: psycopg.Connection) -> None:
        super().__init__()
        self.conn = conn

    def get_tuple(self, config: RunnableConfig) -> CheckpointTuple | None:
        owner = self._owner(config, required=False)
        if owner is None:
            return None
        thread_id = config["configurable"]["thread_id"]
        checkpoint_ns = config["configurable"].get("checkpoint_ns") or ""
        checkpoint_id = get_checkpoint_id(config)
        if checkpoint_id:
            row = self.conn.execute(
                """
                SELECT checkpoint_id, parent_checkpoint_id, checkpoint_type, checkpoint_blob,
                       metadata_type, metadata_blob
                FROM langgraph_checkpoints
                WHERE thread_id = %s AND checkpoint_ns = %s AND checkpoint_id = %s AND owner_id = %s
                """,
                (thread_id, checkpoint_ns, checkpoint_id, owner),
            ).fetchone()
        else:
            row = self.conn.execute(
                """
                SELECT checkpoint_id, parent_checkpoint_id, checkpoint_type, checkpoint_blob,
                       metadata_type, metadata_blob
                FROM langgraph_checkpoints
                WHERE thread_id = %s AND checkpoint_ns = %s AND owner_id = %s
                ORDER BY checkpoint_id DESC
                LIMIT 1
                """,
                (thread_id, checkpoint_ns, owner),
            ).fetchone()
        if row is None:
            return None
        checkpoint = self.serde.loads_typed((row["checkpoint_type"], bytes(row["checkpoint_blob"])))
        metadata = self.serde.loads_typed((row["metadata_type"], bytes(row["metadata_blob"])))
        writes = self.conn.execute(
            """
            SELECT task_id, channel, value_type, value_blob
            FROM langgraph_checkpoint_writes
            WHERE thread_id = %s AND checkpoint_ns = %s AND checkpoint_id = %s AND owner_id = %s
            ORDER BY write_idx
            """,
            (thread_id, checkpoint_ns, row["checkpoint_id"], owner),
        ).fetchall()
        parent = row["parent_checkpoint_id"]
        return CheckpointTuple(
            config={
                "configurable": {
                    "thread_id": thread_id,
                    "checkpoint_ns": checkpoint_ns,
                    "checkpoint_id": row["checkpoint_id"],
                    "owner_id": owner,
                }
            },
            checkpoint=checkpoint,
            metadata=metadata,
            pending_writes=[
                (item["task_id"], item["channel"], self.serde.loads_typed((item["value_type"], bytes(item["value_blob"]))))
                for item in writes
            ],
            parent_config=(
                {
                    "configurable": {
                        "thread_id": thread_id,
                        "checkpoint_ns": checkpoint_ns,
                        "checkpoint_id": parent,
                        "owner_id": owner,
                    }
                }
                if parent
                else None
            ),
        )

    def list(
        self,
        config: RunnableConfig | None,
        *,
        filter: dict[str, Any] | None = None,
        before: RunnableConfig | None = None,
        limit: int | None = None,
    ) -> Iterator[CheckpointTuple]:
        if config is None:
            return
        found = self.get_tuple(config)
        if found is not None:
            yield found

    def put(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: ChannelVersions,
    ) -> RunnableConfig:
        del new_versions
        owner = self._owner(config, required=True)
        thread_id = config["configurable"]["thread_id"]
        checkpoint_ns = config["configurable"].get("checkpoint_ns") or ""
        parent = config["configurable"].get("checkpoint_id")
        review_id = config["configurable"].get("review_id")
        checkpoint_type, checkpoint_blob = self.serde.dumps_typed(checkpoint)
        metadata_type, metadata_blob = self.serde.dumps_typed(metadata)
        self.conn.execute(
            """
            INSERT INTO langgraph_checkpoints (
                thread_id, checkpoint_ns, checkpoint_id, owner_id, review_id, parent_checkpoint_id,
                checkpoint_type, checkpoint_blob, metadata_type, metadata_blob
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (owner_id, thread_id, checkpoint_ns, checkpoint_id)
            DO UPDATE SET
                checkpoint_type = EXCLUDED.checkpoint_type,
                checkpoint_blob = EXCLUDED.checkpoint_blob,
                metadata_type = EXCLUDED.metadata_type,
                metadata_blob = EXCLUDED.metadata_blob
            """,
            (
                thread_id,
                checkpoint_ns,
                checkpoint["id"],
                owner,
                review_id,
                parent,
                checkpoint_type,
                checkpoint_blob,
                metadata_type,
                metadata_blob,
            ),
        )
        return {
            "configurable": {
                "thread_id": thread_id,
                "checkpoint_ns": checkpoint_ns,
                "checkpoint_id": checkpoint["id"],
                "owner_id": owner,
                "review_id": review_id,
            }
        }

    def put_writes(
        self,
        config: RunnableConfig,
        writes: Sequence[tuple[str, Any]],
        task_id: str,
        task_path: str = "",
    ) -> None:
        del task_path
        owner = self._owner(config, required=True)
        thread_id = config["configurable"]["thread_id"]
        checkpoint_ns = config["configurable"].get("checkpoint_ns") or ""
        checkpoint_id = config["configurable"]["checkpoint_id"]
        for idx, (channel, value) in enumerate(writes):
            value_type, value_blob = self.serde.dumps_typed(value)
            self.conn.execute(
                """
                INSERT INTO langgraph_checkpoint_writes (
                    thread_id, checkpoint_ns, checkpoint_id, task_id, write_idx, owner_id,
                    channel, value_type, value_blob
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (owner_id, thread_id, checkpoint_ns, checkpoint_id, task_id, write_idx)
                DO NOTHING
                """,
                (
                    thread_id,
                    checkpoint_ns,
                    checkpoint_id,
                    task_id,
                    idx,
                    owner,
                    channel,
                    value_type,
                    value_blob,
                ),
            )

    def _owner(self, config: RunnableConfig, *, required: bool) -> str | None:
        row = self.conn.execute(
            "SELECT NULLIF(current_setting('app.owner_id', true), '') AS owner_id"
        ).fetchone()
        guc = None if row is None else row["owner_id"]
        if guc is None:
            if required:
                raise CheckpointOwnerError("A checkpoint needs the signed-in owner.")
            return None
        owner = str(guc)
        claimed = config.get("configurable", {}).get("owner_id")
        if claimed is not None and str(claimed) != owner:
            raise CheckpointOwnerError("A checkpoint cannot be read or written for another user.")
        return owner
