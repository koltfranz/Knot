from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

from knot.core.normalize import normalize_text

UNITS = {
    "十": 10,
    "拾": 10,
    "百": 100,
    "佰": 100,
    "千": 1000,
    "仟": 1000,
    "万": 10_000,
    "萬": 10_000,
    "亿": 100_000_000,
    "億": 100_000_000,
    "k": 1000,
    "K": 1000,
    "w": 10_000,
    "W": 10_000,
}

MONEY_UNITS = {"元": 1, "块": 1, "圆": 1}

BIG_UNITS = (("亿", 10**8), ("億", 10**8), ("万", 10**4), ("萬", 10**4), ("w", 10**4), ("W", 10**4))

_STRIP_WORDS = ("人民币", "RMB", "rmb", "CNY", "USD", "美元", "钱", "整", "¥", "￥", "$", " ")

_TOKEN_RE = re.compile(r"(\d+(?:\.\d+)?)([^\d.\s])?")


def _digits(text: str) -> Decimal:
    try:
        return Decimal(text)
    except InvalidOperation as exc:
        raise ValueError(f"无法识别的金额：{text}") from exc


def _unit_value(ch: str) -> Decimal | None:
    if ch in MONEY_UNITS:
        return Decimal(MONEY_UNITS[ch])
    if ch in UNITS:
        return Decimal(UNITS[ch])
    return None


def _parse_small(s: str) -> Decimal:
    total = Decimal(0)
    last_unit: Decimal | None = None
    pos = 0
    for m in _TOKEN_RE.finditer(s):
        if m.start() != pos:
            raise ValueError(f"无法识别的金额：{s}")
        pos = m.end()
        number = _digits(m.group(1))
        unit_char = m.group(2)
        if unit_char is None:
            if last_unit is None:
                total += number
            else:
                total += number * last_unit / 10
            continue
        unit = _unit_value(unit_char)
        if unit is None:
            raise ValueError(f"无法识别的金额：{s}")
        total += number * unit
        last_unit = unit
    if pos != len(s):
        raise ValueError(f"无法识别的金额：{s}")
    return total


def _parse_tail(tail: str, scale: Decimal) -> Decimal:
    if not tail:
        return Decimal(0)
    if any(ch in tail for ch in "十拾百佰千仟"):
        return _parse_cn(tail)
    if _TOKEN_RE.fullmatch(tail) and _TOKEN_RE.fullmatch(tail).group(2) is None:
        return _digits(tail) * scale / 10
    return _parse_cn(tail)


def _parse_cn(s: str) -> Decimal:
    for big, mult in BIG_UNITS:
        if big in s:
            left, _, right = s.partition(big)
            scale = Decimal(mult)
            return (_parse_cn(left) if left else Decimal(1)) * scale + _parse_tail(right, scale)
    return _parse_small(s)


def parse_amount(text: str) -> Decimal:
    """解析命令行金额输入：`38`、`3千`、`1.5万`、`2万3`、`38块5`、`¥38`、`1,234.56`。"""
    s = normalize_text(text).strip()
    if not s:
        raise ValueError("金额不能为空")

    sign = Decimal(1)
    if s[0] in "-−负":
        sign = Decimal(-1)
        s = s[1:].lstrip("号").strip()

    for word in _STRIP_WORDS:
        s = s.replace(word, "")

    while s and s[-1] in "元块圆":
        s = s[:-1]
    s = s.replace(",", "")

    if not s:
        raise ValueError(f"无法识别的金额：{text}")
    return sign * _parse_cn(s)
