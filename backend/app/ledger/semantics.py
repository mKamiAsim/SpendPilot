"""Which posted rows are spending. Card payments, transfers, and cash withdrawals are not."""

from __future__ import annotations

SPENDING_TYPES = frozenset({"purchase"})
CREDIT_TYPES = frozenset({"payment", "refund", "transfer", "cashback"})
LIABILITY_INCREASE = frozenset({"purchase", "fee", "interest", "cash_withdrawal"})
LIABILITY_DECREASE = frozenset({"payment", "refund", "transfer", "cashback"})

CATEGORIES = frozenset(
    {
        "Groceries",
        "Dining",
        "Transport",
        "Utilities",
        "Shopping",
        "Health",
        "Entertainment",
        "Travel",
        "Fees and interest",
        "Transfers",
        "Income",
        "Cash",
        "Other",
    }
)
