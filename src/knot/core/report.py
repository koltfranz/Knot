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


ASSET_ROOT = "资产"
LIABILITY_ROOT = "负债"
EQUITY_ROOT = "权益"


def _root_rows(book: Book, root: str, upto: date | None = None) -> list[tuple[str, Decimal]]:
    rows: dict[str, Decimal] = defaultdict(Decimal)
    for tx in book.transactions:
        if upto is not None and tx.date > upto:
            continue
        for posting in tx.postings:
            if posting.units is None or posting.account.split(":")[0] != root:
                continue
            rows[posting.account] += _amount(book, posting)
    return sorted((name, value) for name, value in rows.items() if not is_zero(value))


def balance_sheet(book: Book, as_of: date | None = None) -> dict:
    """资产负债表（简式）：资产 = 负债 + 权益 + 当期损益。"""
    assets = _root_rows(book, ASSET_ROOT, as_of)
    liabilities = _root_rows(book, LIABILITY_ROOT, as_of)
    equity = _root_rows(book, EQUITY_ROOT, as_of)
    income = _root_rows(book, INCOME_ROOT, as_of)
    expense = _root_rows(book, EXPENSE_ROOT, as_of)

    total_assets = sum((value for _name, value in assets), Decimal(0))
    total_liabilities = sum((value for _name, value in liabilities), Decimal(0))
    total_equity = sum((value for _name, value in equity), Decimal(0))
    profit = -sum((value for _name, value in income), Decimal(0)) - sum(
        (value for _name, value in expense), Decimal(0)
    )
    claims = -total_liabilities - total_equity + profit
    return {
        "日期": (as_of or date.today()).isoformat(),
        "资产": assets,
        "负债": liabilities,
        "权益": equity,
        "当期损益": profit,
        "资产合计": total_assets,
        "负债合计": -total_liabilities,
        "权益合计": -total_equity,
        "负债权益合计": claims,
        "平衡": is_zero(total_assets - claims),
    }


def income_statement(book: Book, start: date | None = None, end: date | None = None) -> dict:
    """利润表（简式）：收入 - 费用 = 净利润。"""
    income: dict[str, Decimal] = defaultdict(Decimal)
    expense: dict[str, Decimal] = defaultdict(Decimal)
    for tx in book.transactions:
        if not _in_range(tx.date, start, end):
            continue
        for posting in tx.postings:
            if posting.units is None:
                continue
            root = posting.account.split(":")[0]
            if root == INCOME_ROOT:
                income[posting.account] += -_amount(book, posting)
            elif root == EXPENSE_ROOT:
                expense[posting.account] += _amount(book, posting)

    income_rows = sorted((name, value) for name, value in income.items() if not is_zero(value))
    expense_rows = sorted((name, value) for name, value in expense.items() if not is_zero(value))
    total_income = sum((value for _name, value in income_rows), Decimal(0))
    total_expense = sum((value for _name, value in expense_rows), Decimal(0))
    return {
        "区间": [
            (start or date.min).isoformat(),
            (end or date.max).isoformat(),
        ],
        "收入": income_rows,
        "费用": expense_rows,
        "收入合计": total_income,
        "费用合计": total_expense,
        "净利润": total_income - total_expense,
    }


OPERATING_KEYWORDS = ("收入", "费用")
INVESTING_KEYWORDS = ("投资", "证券", "基金", "股票")
FINANCING_KEYWORDS = ("贷款", "信用卡", "借")


def _flow_bucket(account: str) -> str:
    root = account.split(":")[0]
    if root == EQUITY_ROOT:
        return "筹资"
    for keyword in FINANCING_KEYWORDS:
        if keyword in account:
            return "筹资"
    for keyword in INVESTING_KEYWORDS:
        if keyword in account:
            return "投资"
    return "经营"


def cash_flow_statement(book: Book, start: date | None = None, end: date | None = None) -> dict:
    """现金流量表（简式）：按对手科目把现金类科目的流动分为经营 / 投资 / 筹资。"""
    buckets: dict[str, Decimal] = defaultdict(Decimal)
    inflow = outflow = Decimal(0)
    for tx in book.transactions:
        if not _in_range(tx.date, start, end):
            continue
        for posting in tx.postings:
            if posting.units is None:
                continue
            if posting.account.split(":")[0] != ASSET_ROOT:
                continue
            value = _amount(book, posting)
            if is_zero(value):
                continue
            bucket = "经营"
            for other in tx.postings:
                if other is posting or other.account.split(":")[0] in (ASSET_ROOT,):
                    continue
                bucket = _flow_bucket(other.account)
                break
            buckets[bucket] += value
            if value > 0:
                inflow += value
            else:
                outflow += value

    return {
        "经营": buckets.get("经营", Decimal(0)),
        "投资": buckets.get("投资", Decimal(0)),
        "筹资": buckets.get("筹资", Decimal(0)),
        "流入合计": inflow,
        "流出合计": outflow,
        "净流量": inflow + outflow,
    }


def render_statement(
    title: str, rows: list[tuple[str, Decimal]], total_label: str, total: Decimal
) -> str:
    lines = [title]
    if rows:
        lines.append(render_pairs(rows))
    lines.append(f"{total_label}：{fmt_amount(total)}")
    return "\n".join(lines)
