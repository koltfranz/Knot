from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from knot.cli.ansi import DIM, style
from knot.cli.commands import abort_on_errors
from knot.core.amount import fmt_amount
from knot.core.date_cn import parse_date, parse_month
from knot.core.loader import load_book
from knot.core.query import Filter, select
from knot.core.table import render


def add_parser(sub) -> None:
    p = sub.add_parser("show", aliases=["查", "s"], help="查看流水")
    p.add_argument("关键词", nargs="*", metavar="关键词", help="匹配科目、收款方或摘要")
    p.add_argument("--月", "--month", dest="month", metavar="月份", help="如 2026-09 或 9月")
    p.add_argument("--年", "--year", dest="year", metavar="年份", help="如 2026")
    p.add_argument("--从", "--from", dest="date_from", metavar="日期")
    p.add_argument("--到", "--to", dest="date_to", metavar="日期")
    p.add_argument("--科目", "--account", dest="account", metavar="科目")
    p.add_argument("--标签", dest="tags", action="append", metavar="标签")
    p.add_argument("--收款方", dest="payee", metavar="名称")
    p.add_argument("--最少金额", dest="min_amount", metavar="金额")
    p.add_argument("--币种", dest="currency", metavar="币种")
    p.add_argument("--条数", dest="limit", type=int, metavar="N")
    p.add_argument("--json", dest="as_json", action="store_true", help="输出结构化 JSON")
    p.add_argument("--sql", dest="sql", metavar="语句", help="用 SQL 子集查询（见 语法大全）")
    p.set_defaults(func=run)


def _filter(args, aliases) -> Filter:
    date_from: date | None = None
    date_to: date | None = None
    if args.month:
        date_from, date_to = parse_month(args.month)
    elif args.year:
        date_from, date_to = parse_month(f"{args.year}-1")
        date_to = parse_month(f"{args.year}-12")[1]
    if args.date_from:
        date_from = parse_date(args.date_from)
    if args.date_to:
        date_to = parse_date(args.date_to)

    account = None
    if args.account:
        resolution = aliases.resolve(args.account)
        account = resolution.target or args.account

    min_amount = None
    if args.min_amount:
        from knot.core.number_cn import parse_amount

        min_amount = abs(parse_amount(args.min_amount))

    return Filter(
        account=account,
        date_from=date_from,
        date_to=date_to,
        tags=frozenset(args.tags or []),
        payee=args.payee,
        min_amount=min_amount,
        currency=args.currency,
        limit=args.limit,
        keywords=list(args.关键词 or []),
    )


def _records(transactions) -> list[dict]:
    records = []
    for tx in transactions:
        records.append(
            {
                "日期": tx.date.isoformat(),
                "标志": tx.flag.value,
                "收款方": tx.payee,
                "摘要": tx.narration,
                "标签": sorted(tx.tags),
                "链接": sorted(tx.links),
                "分录": [
                    {
                        "科目": p.account,
                        "金额": fmt_amount(p.units.number) if p.units else None,
                        "币种": p.units.currency if p.units else None,
                        "对手科目": p.counterparty,
                        "自动配平": p.generated,
                    }
                    for p in tx.postings
                ],
                "来源": f"{tx.src_file}:{tx.src_line_start}",
            }
        )
    return records


def run(args) -> int:
    result, book, diags = load_book(Path(args.ledger))
    if abort_on_errors(diags):
        return 1

    if getattr(args, "sql", None):
        from knot.core.sql import execute

        outcome = execute(book, args.sql)
        if args.as_json:
            print(
                json.dumps(
                    {"字段": outcome["字段"], "行": outcome["行"], "条数": outcome["条数"]},
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return 0
        print(
            render(
                outcome["字段"],
                outcome["行"],
                aligns=["left"] + ["right"] * (len(outcome["字段"]) - 1),
            )
        )
        print(style(f"共 {outcome['条数']} 行", DIM))
        return 0

    transactions = select(book.transactions, _filter(args, result.aliases))

    if args.as_json:
        print(json.dumps(_records(transactions), ensure_ascii=False, indent=2))
        return 0

    rows: list[list[str]] = []
    for tx in transactions:
        name = tx.payee or tx.narration
        for posting in tx.postings:
            rows.append(
                [
                    tx.date.isoformat(),
                    tx.flag.value,
                    name,
                    posting.account,
                    fmt_amount(posting.units.number) if posting.units else "",
                    posting.units.currency if posting.units else "",
                ]
            )

    if not rows:
        print(style("没有匹配的流水", DIM))
        return 0
    print(
        render(
            ["日期", "标志", "摘要/收款方", "科目", "金额", "币种"],
            rows,
            aligns=["left", "left", "left", "left", "right", "left"],
        )
    )
    print(style(f"共 {len(transactions)} 笔交易", DIM))
    return 0
