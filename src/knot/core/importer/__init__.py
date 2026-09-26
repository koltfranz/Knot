"""账单导入：微信 / 支付宝 / 银行 CSV。"""

from knot.core.importer import alipay, bank, wechat
from knot.core.importer.base import (
    EXPENSE,
    INCOME,
    SKIP,
    ImportResult,
    ImportRow,
    ImportStats,
    build_transaction,
    column_index,
    existing_keys,
    find_header,
    parse_date_cell,
    parse_money,
    read_table,
    rows_from_table,
    split_duplicates,
)

SOURCES = {
    "微信": wechat,
    "wechat": wechat,
    "支付宝": alipay,
    "alipay": alipay,
    "银行": bank,
    "bank": bank,
}

__all__ = [
    "EXPENSE",
    "INCOME",
    "SKIP",
    "SOURCES",
    "ImportResult",
    "ImportRow",
    "ImportStats",
    "alipay",
    "bank",
    "build_transaction",
    "column_index",
    "existing_keys",
    "find_header",
    "parse_date_cell",
    "parse_money",
    "read_table",
    "rows_from_table",
    "split_duplicates",
    "wechat",
]
