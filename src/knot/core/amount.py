from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation, getcontext

getcontext().prec = 28

CENT = Decimal("0.01")
TOLERANCE = Decimal("0.005")


def q2(d: Decimal) -> Decimal:
    return d.quantize(CENT, rounding=ROUND_HALF_UP)


def parse_decimal(text: str) -> Decimal:
    try:
        return Decimal(text.replace(",", "").strip())
    except InvalidOperation as exc:
        raise ValueError(f"无法识别的金额：{text}") from exc


def is_zero(d: Decimal) -> bool:
    return abs(d) < TOLERANCE


def fmt_amount(d: Decimal, places: int = 2) -> str:
    quant = Decimal(1).scaleb(-places)
    return f"{d.quantize(quant, rounding=ROUND_HALF_UP):,}"
