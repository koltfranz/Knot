"""支付宝账单解析。

格式：GBK（常见），前置说明若干行，表头含
`交易创建时间,交易对方,商品名称,金额（元）,收/支,交易状态,...`
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

NAME = "支付宝"
REQUIRED = ("交易", "金额")
COLUMNS = {
    "date": ("交易创建时间", "交易时间", "付款时间"),
    "payee": ("交易对方",),
    "memo": ("商品名称", "商品说明", "备注"),
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
                    message="未找到支付宝账单表头（需要包含 交易创建时间 / 交易对方 / 金额）",
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
