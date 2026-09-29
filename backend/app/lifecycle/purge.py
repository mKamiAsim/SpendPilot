"""Drop ledger rows and derived memory older than 18 months.

An instalment with a remaining balance keeps its plan and repayments so the
monthly figure still has a source. A fully repaid plan older than the cutoff
goes away with its repayments.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

CUTOFF = "(CURRENT_DATE - INTERVAL '18 months')::date"

STATEMENTS = (
    f"DELETE FROM memories WHERE created_at::date < {CUTOFF}",
    f"DELETE FROM langgraph_checkpoint_writes WHERE created_at::date < {CUTOFF}",
    f"DELETE FROM langgraph_checkpoints WHERE created_at::date < {CUTOFF}",
    f"DELETE FROM review_checkpoints WHERE created_at::date < {CUTOFF}",
    f"DELETE FROM findings WHERE created_at::date < {CUTOFF}",
    f"DELETE FROM briefings WHERE created_at::date < {CUTOFF}",
    f"DELETE FROM targets WHERE created_at::date < {CUTOFF}",
    f"DELETE FROM scenarios WHERE created_at::date < {CUTOFF}",
    f"DELETE FROM reviews WHERE created_at::date < {CUTOFF}",
    f"DELETE FROM investigations WHERE created_at::date < {CUTOFF}",
    f"DELETE FROM snapshots WHERE created_at::date < {CUTOFF}",
    f"DELETE FROM cash_entries WHERE posted_on < {CUTOFF}",
    f"DELETE FROM posted_transactions WHERE posted_on < {CUTOFF}",
    f"DELETE FROM statements WHERE period_end < {CUTOFF}",
    f"""
    DELETE FROM instalment_plans
    WHERE posted_on < {CUTOFF}
      AND principal <= (
          SELECT COALESCE(SUM(instalment_repayments.amount), 0)
          FROM instalment_repayments
          WHERE instalment_repayments.plan_id = instalment_plans.id
      )
    """,
)


async def purge_expired(db: AsyncSession) -> None:
    for statement in STATEMENTS:
        await db.execute(text(statement))
