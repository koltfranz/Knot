"""银行流水解析（通用列映射）。

支持两种常见形态：
1. 单列金额（可为负）；2. 收入 / 支出 两列（借方 / 贷方）。
表头需包含 日期 与 金额（或 收入/支出 列）。
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from knot.core.diagnostic import Diagnostic
from knot.core.importer.base import (
    EXPENSE,
    INCOME,
    ImportResult,
    ImportRow,
    cell_value,
    column_index,
    find_header,
    parse_date_cell,
    parse_money,
    read_table,
    rows_from_table,
)

NAME = "银行"
REQUIRED = ("日期", "金额")
REQUIRED_SPLIT = ("日期", "收入")

COLUMNS = {
    "date": ("交易日期", "记账日期", "日期", "交易时间"),
    "payee": ("交易对方", "对方户名", "对手信息"),
    "memo": ("摘要", "备注", "用途", "说明"),
    "amount": ("金额", "发生额", "交易金额"),
    "income": ("收入", "贷方"),
    "expense": ("支出", "借方"),
}


def parse(path: Path) -> ImportResult:
    rows = read_table(path)
    header_index = find_header(rows, REQUIRED)
    split_columns = False
    if header_index is None:
        header_index = find_header(rows, REQUIRED_SPLIT)
        split_columns = header_index is not None
    if header_index is None:
        return ImportResult(
            diagnostics=[
                Diagnostic(
                    level="error",
                    file=str(path),
                    line=len(rows),
                    col=1,
                    message="未找到银行流水表头（需要 日期 + 金额，或 日期 + 收入/支出）",
                )
            ]
        )

    header = rows[header_index]
    column_map = {name: column_index(header, *candidates) for name, candidates in COLUMNS.items()}
    if split_columns:
        return _parse_split(path, rows, header_index, column_map)

    parsed, diagnostics, failed = rows_from_table(rows, header_index, column_map)
    result = ImportResult(rows=parsed, diagnostics=diagnostics)
    result.stats.total = len(parsed) + failed
    result.stats.failed = failed
    return result


def _parse_split(
    path: Path, rows: list[list[str]], header_index: int, column_map: dict
) -> ImportResult:
    diagnostics: list[Diagnostic] = []
    parsed: list[ImportRow] = []
    failed = 0

    for line_no, row in enumerate(rows[header_index + 1 :], start=header_index + 2):
        if not any(cell.strip() for cell in row):
            continue

        when = parse_date_cell(cell_value(row, column_map, "date"))
        income = parse_money(cell_value(row, column_map, "income"))
        expense = parse_money(cell_value(row, column_map, "expense"))
        if when is None or (income is None and expense is None):
            failed += 1
            diagnostics.append(
                Diagnostic(
                    level="warning",
                    file=str(path),
                    line=line_no,
                    col=1,
                    message="无法解析日期或金额，已跳过该行",
                )
            )
            continue

        if income is not None and income != Decimal(0):
            amount, direction = abs(income), INCOME
        elif expense is not None and expense != Decimal(0):
            amount, direction = abs(expense), EXPENSE
        else:
            continue

        parsed.append(
            ImportRow(
                date=when,
                amount=amount,
                direction=direction,
                payee=cell_value(row, column_map, "payee")
                or cell_value(row, column_map, "memo")
                or "未知",
                memo=cell_value(row, column_map, "memo"),
                line_no=line_no,
                raw=row,
            )
        )

    result = ImportResult(rows=parsed, diagnostics=diagnostics)
    result.stats.total = len(parsed) + failed
    result.stats.failed = failed
    return result
