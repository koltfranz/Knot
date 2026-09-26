from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

from knot.cli.ansi import GREEN, YELLOW, style
from knot.cli.commands import abort_on_errors
from knot.core.diagnostic import render_all
from knot.core.importer import SOURCES
from knot.core.importer.base import (
    ImportResult,
    build_transaction,
    existing_keys,
    split_duplicates,
)
from knot.core.loader import load_book
from knot.core.normalize import KnotError
from knot.core.writer import insert_transaction, target_year_file


def add_parser(sub) -> None:
    p = sub.add_parser("import", aliases=["导入"], help="导入账单 CSV")
    p.add_argument("来源", metavar="来源", help="微信 / 支付宝 / 银行")
    p.add_argument("文件", nargs="+", metavar="文件")
    p.add_argument(
        "--账户", dest="account", metavar="科目", help="账单对应的资金科目，默认 default_asset"
    )
    p.add_argument(
        "--试运行", "--dry-run", dest="dry_run", action="store_true", help="只报告不写入"
    )
    p.add_argument("--json", dest="as_json", action="store_true")
    p.set_defaults(func=run)


def _source(name: str):
    module = SOURCES.get(name) or SOURCES.get(name.lower())
    if module is None:
        raise KnotError(f"未知账单来源：{name}（可选 {' / '.join(sorted(set(SOURCES)))}）")
    return module


def run(args) -> int:
    ledger = Path(args.ledger)
    result, book, diags = load_book(ledger, missing_ok=True)
    if abort_on_errors(diags):
        return 1

    module = _source(args.来源)
    source_account = args.account or book.options.default_asset
    resolution = result.aliases.resolve(source_account)
    source_account = resolution.target or source_account

    known = existing_keys(book)
    written: Counter = Counter()
    payload: dict[str, dict] = {}
    diagnostics = []
    imported_total = 0
    uncategorized_total = 0

    for raw_path in args.文件:
        path = Path(raw_path)
        if not path.exists():
            raise KnotError(f"文件不存在：{path}")
        parsed: ImportResult = module.parse(path)
        diagnostics.extend(parsed.diagnostics)
        if any(d.level == "error" for d in parsed.diagnostics):
            payload[str(path)] = {"错误": [d.message for d in parsed.diagnostics]}
            continue

        kept, duplicates = split_duplicates(parsed.rows, known + written)
        transactions = [
            build_transaction(
                row,
                source_account=source_account,
                rules=result.rules,
                default_target=book.options.default_income,
                currency=book.options.operating_currency,
            )
            for row in kept
        ]
        uncategorized = sum(1 for tx in transactions if tx.flag.value == "?")

        if not args.dry_run:
            for transaction in transactions:
                target = target_year_file(ledger, transaction.date.year, result.files)
                insert_transaction(target, transaction)
            written.update(row.key() for row in kept)

        imported_total += len(transactions)
        uncategorized_total += uncategorized
        payload[str(path)] = {
            "总行数": parsed.stats.total,
            "可导入": len(transactions),
            "重复": len(duplicates),
            "待分类": uncategorized,
            "解析失败": parsed.stats.failed,
        }

    if diagnostics:
        print(render_all(diagnostics), file=sys.stderr)

    if args.as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    for path, stats in payload.items():
        if "错误" in stats:
            print(style(f"导入失败：{path}", YELLOW) + f"（{stats['错误'][0]}）")
            continue
        head = "试运行" if args.dry_run else "已导入"
        print(style(f"{head}：{path}", GREEN))
        print(
            f"  总 {stats['总行数']} 行 · 可导入 {stats['可导入']} · "
            f"重复 {stats['重复']} · 待分类 {stats['待分类']} · 解析失败 {stats['解析失败']}"
        )

    if args.dry_run:
        print(style("（试运行未写入，去掉 --试运行 即写入账本）", YELLOW))
    elif imported_total:
        print(
            f"共写入 {imported_total} 笔：待分类 {uncategorized_total} 笔标 ?，"
            f"可在 规则/分类规则.knot 补充规则后重新导入"
        )
    return 0
