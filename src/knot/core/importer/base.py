"""账单导入基座：编码探测、表头定位、字段解析、指纹去重。"""

from __future__ import annotations

import csv
import io
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

from knot.core.amount import fmt_amount
from knot.core.book import Book
from knot.core.date_cn import parse_date
from knot.core.diagnostic import Diagnostic
from knot.core.model import Amount, Flag, Posting, Transaction
from knot.core.normalize import normalize_text, sniff_and_read
from knot.core.rules import RuleTable

EXPENSE = "支出"
INCOME = "收入"
SKIP = "不计收支"

UNCATEGORIZED_ACCOUNT = "费用:待分类"

_MONEY_RE = re.compile(r"[-+]?[\d,]+(?:\.\d+)?")


@dataclass
class ImportRow:
    date: date
    amount: Decimal
    direction: str
    payee: str
    memo: str = ""
    line_no: int = 0
    raw: list[str] = field(default_factory=list)

    def key(self) -> tuple[str, str, str]:
        return (self.date.isoformat(), fmt_amount(abs(self.amount)), self.payee)


@dataclass
class ImportStats:
    total: int = 0
    imported: int = 0
    skipped: int = 0
    duplicate: int = 0
    uncategorized: int = 0
    failed: int = 0

    def as_dict(self) -> dict:
        return {
            "总行数": self.total,
            "可导入": self.imported,
            "重复": self.duplicate,
            "跳过": self.skipped,
            "待分类": self.uncategorized,
            "解析失败": self.failed,
        }


@dataclass
class ImportResult:
    rows: list[ImportRow] = field(default_factory=list)
    diagnostics: list[Diagnostic] = field(default_factory=list)
    stats: ImportStats = field(default_factory=ImportStats)


def read_table(path: Path) -> list[list[str]]:
    text = sniff_and_read(path)
    reader = csv.reader(io.StringIO(text))
    return [row for row in reader]


def find_header(rows: list[list[str]], required: tuple[str, ...], max_scan: int = 80) -> int | None:
    for index, row in enumerate(rows[:max_scan]):
        joined = ",".join(cell.strip() for cell in row)
        if all(key in joined for key in required):
            return index
    return None


def column_index(header: list[str], *candidates: str) -> int | None:
    for index, cell in enumerate(header):
        name = normalize_text(cell).strip()
        for candidate in candidates:
            if candidate in name:
                return index
    return None


def parse_money(text: str) -> Decimal | None:
    cleaned = normalize_text(text).replace("¥", "").replace("$", "").strip()
    match = _MONEY_RE.search(cleaned.replace(" ", ""))
    if match is None:
        return None
    try:
        return Decimal(match.group().replace(",", ""))
    except InvalidOperation:
        return None


def parse_date_cell(text: str, today: date | None = None) -> date | None:
    cleaned = normalize_text(text).strip()
    if not cleaned:
        return None
    head = cleaned.split(" ")[0].split("T")[0]
    try:
        return parse_date(head, today)
    except ValueError:
        return None


def _direction(text: str) -> str:
    cleaned = normalize_text(text).strip()
    if "不计" in cleaned or cleaned in ("其他", "/"):
        return SKIP
    if "收入" in cleaned or cleaned in ("收", "入账"):
        return INCOME
    if "支出" in cleaned or cleaned in ("支", "出账"):
        return EXPENSE
    return SKIP


def cell_value(row: list[str], column_map: dict[str, int | None], field_name: str) -> str:
    index = column_map.get(field_name)
    return row[index].strip() if index is not None and index < len(row) else ""


def rows_from_table(
    rows: list[list[str]],
    header_index: int,
    column_map: dict[str, int | None],
) -> tuple[list[ImportRow], list[Diagnostic], int]:
    header = rows[header_index]
    diagnostics: list[Diagnostic] = []
    parsed: list[ImportRow] = []
    failed = 0
    widest = max((index or 0) for index in column_map.values())

    for line_no, row in enumerate(rows[header_index + 1 :], start=header_index + 2):
        if not any(cell.strip() for cell in row):
            continue
        if len(row) <= widest:
            failed += 1
            diagnostics.append(
                Diagnostic(
                    level="warning",
                    file=header_name(header),
                    line=line_no,
                    col=1,
                    message="列数不足，已跳过该行",
                )
            )
            continue

        when = parse_date_cell(cell_value(row, column_map, "date"))
        amount = parse_money(cell_value(row, column_map, "amount"))
        has_direction = column_map.get("direction") is not None
        direction = _direction(cell_value(row, column_map, "direction")) if has_direction else ""
        if not has_direction:
            direction = INCOME if amount is not None and amount < 0 else EXPENSE

        if when is None or amount is None:
            failed += 1
            diagnostics.append(
                Diagnostic(
                    level="warning",
                    file=header_name(header),
                    line=line_no,
                    col=1,
                    message="无法解析日期或金额，已跳过该行",
                    snippet=",".join(row)[:80],
                )
            )
            continue
        if direction == SKIP:
            continue

        parsed.append(
            ImportRow(
                date=when,
                amount=abs(amount),
                direction=direction,
                payee=cell_value(row, column_map, "payee")
                or cell_value(row, column_map, "memo")
                or "未知",
                memo=cell_value(row, column_map, "memo"),
                line_no=line_no,
                raw=row,
            )
        )
    return parsed, diagnostics, failed


def header_name(header: list[str]) -> str:
    return ",".join(cell.strip() for cell in header[:3])


def existing_keys(book: Book) -> Counter:
    counter: Counter = Counter()
    for tx in book.transactions:
        for posting in tx.postings:
            if posting.units is None or posting.units.number <= 0:
                continue
            counter[
                (
                    tx.date.isoformat(),
                    fmt_amount(abs(posting.units.number)),
                    tx.payee or tx.narration,
                )
            ] += 1
    return counter


def split_duplicates(
    rows: list[ImportRow], known: Counter
) -> tuple[list[ImportRow], list[ImportRow]]:
    """按「日期 + 金额 + 收款方」出现次序去重，与账本已有条目对账。"""
    seen: Counter = Counter()
    kept: list[ImportRow] = []
    duplicates: list[ImportRow] = []
    for row in rows:
        key = row.key()
        seen[key] += 1
        if seen[key] <= known.get(key, 0):
            duplicates.append(row)
        else:
            kept.append(row)
    return kept, duplicates


def build_transaction(
    row: ImportRow,
    *,
    source_account: str,
    rules: RuleTable,
    default_target: str,
    currency: str,
) -> Transaction:
    """把导入行转换为交易；未匹配分类规则时落到 费用:待分类 并标 ? 标志。"""
    matched = rules.match(row.payee)
    if row.direction == INCOME:
        account = matched or default_target
        posting = Posting(account=account, units=Amount(-row.amount, currency))
        counter = Posting(account=source_account, units=Amount(row.amount, currency))
    else:
        account = matched or UNCATEGORIZED_ACCOUNT
        posting = Posting(account=account, units=Amount(row.amount, currency))
        counter = Posting(account=source_account, units=Amount(-row.amount, currency))

    flag = Flag.OK if matched else Flag.UNKNOWN
    return Transaction(
        date=row.date,
        flag=flag,
        payee=row.payee,
        narration=row.memo,
        postings=[posting, counter],
        meta={"导入": row.memo or row.payee},
    )
