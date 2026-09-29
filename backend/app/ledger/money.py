from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

TOLERANCE = Decimal("0.01")
QUANT = Decimal("0.01")


def money(value: Decimal | str | int) -> Decimal:
    return Decimal(value).quantize(QUANT, rounding=ROUND_HALF_UP)


def money_str(value: Decimal) -> str:
    return f"{money(value):.2f}"
