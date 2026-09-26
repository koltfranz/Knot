"""微信支付账单解析。

格式：UTF-8（可带 BOM），前置说明若干行，表头含
`交易时间,交易类型,交易对方,商品,收/支,金额(元),支付方式,当前状态,交易单号,商户单号,备注`
"""

from __future__ import annotations

from pathlib import Path

from knot.core.diagnostic import Diagnostic
from knot.core.importer.base import (
    ImportResult,
    column_index,
    find_header,
    read_table,
    rows_from_table,
)

NAME = "微信"
REQUIRED = ("交易时间", "交易对方", "金额")
COLUMNS = {
    "date": ("交易时间",),
    "payee": ("交易对方",),
    "memo": ("商品", "备注"),
    "direction": ("收/支", "收支"),
    "amount": ("金额",),
}


def parse(path: Path) -> ImportResult:
    rows = read_table(path)
    header_index = find_header(rows, REQUIRED)
    if header_index is None:
        return ImportResult(
            diagnostics=[
                Diagnostic(
                    level="error",
                    file=str(path),
                    line=len(rows),
                    col=1,
                    message="未找到微信账单表头（需要包含 交易时间 / 交易对方 / 金额）",
                )
            ]
        )

    header = rows[header_index]
    column_map = {name: column_index(header, *candidates) for name, candidates in COLUMNS.items()}
    parsed, diagnostics, failed = rows_from_table(rows, header_index, column_map)

    result = ImportResult(rows=parsed, diagnostics=diagnostics)
    result.stats.total = len(parsed) + failed
    result.stats.failed = failed
    return result
