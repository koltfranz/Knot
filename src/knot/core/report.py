"""报表聚合：全部输入为 Decimal，输出结构化数据或对齐文本。"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

from knot.core.amount import fmt_amount, is_zero
from knot.core.book import Book, signed_value
from knot.core.table import render

INCOME_ROOT = "收入"
EXPENSE_ROOT = "费用"


def month_key(when: date) -> str:
    return f"{when.year:04d}-{when.month:02d}"


def month_range(start: date | None, end: date | None, known: list[str]) -> list[str]:
    if not known:
        return []
    start_key = month_key(start) if start else min(known)
    end_key = month_key(end) if end else max(known)
    months: list[str] = []
    year, month = int(start_key[:4]), int(start_key[5:7])
    while f"{year:04d}-{month:02d}" <= end_key:
        months.append(f"{year:04d}-{month:02d}")
        month += 1
        if month > 12:
            year, month = year + 1, 1
    return months


def _in_range(when: date, start: date | None, end: date | None) -> bool:
    if start and when < start:
        return False
    return not (end and when > end)


def _amount(book: Book, posting) -> Decimal:
    if posting.cost is not None and posting.units.currency:
        return signed_value(posting) or Decimal(0)
    return posting.units.number


def monthly_flow(book: Book, start: date | None = None, end: date | None = None) -> list[dict]:
    """每月收入、支出与净额（正数表示金额大小，收入已取反为正）。"""
    income: dict[str, Decimal] = defaultdict(Decimal)
    expense: dict[str, Decimal] = defaultdict(Decimal)
    observed: list[str] = []

    for tx in book.transactions:
        if not _in_range(tx.date, start, end):
            continue
        key = month_key(tx.date)
        if key not in observed:
            observed.append(key)
        for posting in tx.postings:
            if posting.units is None:
                continue
            root = posting.account.split(":")[0]
            amount = _amount(book, posting)
            if root == INCOME_ROOT:
                income[key] += -amount
            elif root == EXPENSE_ROOT:
                expense[key] += amount

    months = month_range(start, end, sorted(set(observed) | set(income) | set(expense)))
    rows = []
    for key in months:
        earned = income.get(key, Decimal(0))
        spent = expense.get(key, Decimal(0))
        rows.append({"月份": key, "收入": earned, "支出": spent, "净额": earned - spent})
    return rows


def net_worth_trend(book: Book, start: date | None = None, end: date | None = None) -> list[dict]:
    """每月月末净资产（资产 + 负债，负债为负值）。"""
    months = month_range(start, end, sorted({month_key(tx.date) for tx in book.transactions}))
    rows = []
    for key in months:
        year, month = int(key[:4]), int(key[5:7])
        last_day = (
            date(year, 12, 31) if month == 12 else date(year, month + 1, 1) - timedelta(days=1)
        )
        rows.append({"月份": key, **book.net_worth(last_day)})
    return rows


def expense_by_category(
    book: Book,
    start: date | None = None,
    end: date | None = None,
    depth: int = 2,
    top: int | None = None,
) -> list[tuple[str, Decimal]]:
    totals: dict[str, Decimal] = defaultdict(Decimal)
    for tx in book.transactions:
        if not _in_range(tx.date, start, end):
            continue
        for posting in tx.postings:
            if posting.units is None:
                continue
            if posting.account.split(":")[0] != EXPENSE_ROOT:
                continue
            amount = _amount(book, posting)
            parts = posting.account.split(":")
            label = ":".join(parts[: max(1, depth)])
            totals[label] += amount

    rows = [(name, value) for name, value in totals.items() if not is_zero(value)]
    rows.sort(key=lambda item: (-item[1], item[0]))
    if top is not None:
        rows = rows[:top]
    return rows


def category_trend(
    book: Book, account: str, start: date | None = None, end: date | None = None
) -> list[dict]:
    totals: dict[str, Decimal] = defaultdict(Decimal)
    for tx in book.transactions:
        if not _in_range(tx.date, start, end):
            continue
        for posting in tx.postings:
            if posting.units is None:
                continue
            if posting.account != account and not posting.account.startswith(account + ":"):
                continue
            totals[month_key(tx.date)] += posting.units.number
    months = month_range(start, end, sorted(totals))
    return [{"月份": key, "金额": totals.get(key, Decimal(0))} for key in months]


def balance_over_time(
    book: Book, account: str, start: date | None = None, end: date | None = None
) -> list[dict]:
    months = month_range(start, end, sorted({month_key(tx.date) for tx in book.transactions}))
    rows = []
    for key in months:
        year, month = int(key[:4]), int(key[5:7])
        last_day = (
            date(year, 12, 31) if month == 12 else date(year, month + 1, 1) - timedelta(days=1)
        )
        totals = book.balance_of(account, upto=last_day)
        rows.append({"月份": key, "余额": sum(totals.values(), Decimal(0))})
    return rows


def render_summary(summary: dict) -> str:
    lines = [f"交易数：{summary.get('交易数', 0)}"]
    blocks = [
        ("科目余额", summary.get("科目余额", {})),
        ("收入", summary.get("收入", {})),
        ("支出", summary.get("支出", {})),
        ("净资产", summary.get("净资产", {})),
    ]
    for title, data in blocks:
        if not data:
            continue
        lines.append("")
        lines.append(title)
        lines.extend(f"  {key}  {value}" for key, value in sorted(data.items()))
    return "\n".join(lines)


def render_monthly_flow(rows: list[dict]) -> str:
    table = [
        [row["月份"], fmt_amount(row["收入"]), fmt_amount(row["支出"]), fmt_amount(row["净额"])]
        for row in rows
    ]
    return render(
        ["月份", "收入", "支出", "净额"], table, aligns=["left", "right", "right", "right"]
    )


def render_pairs(rows: list[tuple[str, Decimal]], left: str = "科目", right: str = "金额") -> str:
    table = [[name, fmt_amount(value)] for name, value in rows]
    return render([left, right], table, aligns=["left", "right"])


def render_trend(rows: list[dict], value_key: str, label: str = "金额") -> str:
    table = [[row["月份"], fmt_amount(row[value_key])] for row in rows]
    return render(["月份", label], table, aligns=["left", "right"])
