"""预算与进度：把 `budget` 指令与实际发生额对比。"""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import Decimal

from knot.core.amount import is_zero
from knot.core.book import Book
from knot.core.keywords import canonical_period, period_spelling
from knot.core.model import Budget
from knot.core.report import _amount, month_key


def budget_directives(book: Book) -> list[Budget]:
    return [d for d in book.directives if isinstance(d, Budget)]


def month_of(budget: Budget, when: date | None = None) -> str:
    return month_key(when or budget.date)


def actual_for(book: Book, account: str, month: str) -> Decimal:
    total = Decimal(0)
    for tx in book.transactions:
        if month_key(tx.date) != month:
            continue
        for posting in tx.postings:
            if posting.units is None:
                continue
            if posting.account != account and not posting.account.startswith(account + ":"):
                continue
            total += _amount(book, posting)
    return total


def latest_month(book: Book) -> str:
    months = [month_key(tx.date) for tx in book.transactions]
    if months:
        return max(months)
    budgets = budget_directives(book)
    return month_of(budgets[0]) if budgets else month_key(date.today())


def rows(book: Book, month: str | None = None) -> list[dict]:
    """预算进度：每个预算指令一行；不指定月份时取最近有交易的月份。"""
    target_month = month or latest_month(book)
    result = []
    for budget in budget_directives(book):
        period = canonical_period(budget.period) or "monthly"
        spent = actual_for(book, budget.account, target_month)
        planned = budget.amount.number
        remaining = planned - spent
        ratio = float(spent / planned) if planned else 0.0
        result.append(
            {
                "科目": budget.account,
                "周期": period_spelling(period, "zh"),
                "月份": target_month,
                "预算": planned,
                "实际": spent,
                "剩余": remaining,
                "进度": ratio,
                "超支": not is_zero(remaining) and remaining < 0 and spent > planned,
                "币种": budget.amount.currency or book.options.operating_currency,
            }
        )
    return result


def by_account(book: Book, month: str | None = None) -> dict[str, Decimal]:
    totals: dict[str, Decimal] = defaultdict(Decimal)
    for row in rows(book, month):
        totals[row["科目"]] += row["预算"]
    return dict(totals)


def summary(book: Book, month: str | None = None) -> dict:
    items = rows(book, month)
    planned = sum((item["预算"] for item in items), Decimal(0))
    spent = sum((item["实际"] for item in items), Decimal(0))
    over = [item["科目"] for item in items if item["超支"]]
    return {
        "月份": items[0]["月份"] if items else (month or ""),
        "预算合计": planned,
        "实际合计": spent,
        "剩余合计": planned - spent,
        "超支科目": over,
        "条数": len(items),
    }
