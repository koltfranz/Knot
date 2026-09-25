from __future__ import annotations

import calendar
import copy
from datetime import date, timedelta

from knot.core.model import Directive, Flag, Recur, Transaction

PERIOD_ALIASES = {
    "每天": "daily",
    "每周": "weekly",
    "每月": "monthly",
    "每季度": "quarterly",
    "每年": "yearly",
}

MAX_OCCURRENCES = 10_000


def normalize_period(period: str) -> str:
    return PERIOD_ALIASES.get(period, period.lower())


def _add_months(d: date, months: int) -> date:
    total = d.month - 1 + months
    year = d.year + total // 12
    month = total % 12 + 1
    day = min(d.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def _step(d: date, period: str) -> date:
    if period == "daily":
        return d + timedelta(days=1)
    if period == "weekly":
        return d + timedelta(days=7)
    if period == "monthly":
        return _add_months(d, 1)
    if period == "quarterly":
        return _add_months(d, 3)
    if period == "yearly":
        return _add_months(d, 12)
    raise ValueError(f"未知周期：{period}")


def occurrences(period: str, start: date, end: date | None) -> list[date]:
    period = normalize_period(period)
    if end is None or end < start:
        return [start]
    dates: list[date] = []
    current = start
    while current <= end and len(dates) < MAX_OCCURRENCES:
        dates.append(current)
        current = _step(current, period)
    return dates


def expand_recur(directives: list[Directive]) -> list[Directive]:
    expanded: list[Directive] = []
    for directive in directives:
        if not isinstance(directive, Recur):
            expanded.append(directive)
            continue
        for when in occurrences(directive.period, directive.date_from, directive.date_to):
            postings = copy.deepcopy(directive.postings)
            expanded.append(
                Transaction(
                    date=when,
                    flag=Flag.OK,
                    payee=None,
                    narration=directive.description,
                    postings=postings,
                    meta={"定期": directive.period},
                    src_file=directive.src_file,
                    src_line_start=directive.src_line_start,
                    src_line_end=directive.src_line_end,
                )
            )
    return expanded
