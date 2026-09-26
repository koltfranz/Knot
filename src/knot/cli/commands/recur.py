from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from knot.cli.ansi import DIM, style
from knot.cli.commands import abort_on_errors
from knot.core.amount import fmt_amount
from knot.core.date_cn import parse_month
from knot.core.loader import load_book
from knot.core.model import Recur
from knot.core.recur import occurrences
from knot.core.report import month_key
from knot.core.table import render


def add_parser(sub) -> None:
    p = sub.add_parser("recur", aliases=["定期"], help="定期交易模板与展开预览")
    p.add_argument("--月", "--month", dest="month", metavar="月份", help="查看该月展开出的交易")
    p.add_argument("--json", dest="as_json", action="store_true")
    p.set_defaults(func=run)


def templates(book) -> list[Recur]:
    return [d for d in book.directives if isinstance(d, Recur)]


def next_occurrence(template: Recur, after: date) -> date | None:
    dates = occurrences(template.period, template.date_from, template.date_to)
    for when in dates:
        if when > after:
            return when
    return None


def run(args) -> int:
    _result, book, diags = load_book(Path(args.ledger))
    if abort_on_errors(diags):
        return 1

    today = date.today()
    items = templates(book)
    rows = [
        {
            "周期": item.period,
            "说明": item.description,
            "起": item.date_from.isoformat(),
            "止": item.date_to.isoformat() if item.date_to else "—",
            "下次": (next_occurrence(item, today) or item.date_from).isoformat(),
            "分录": len(item.postings),
            "来源": f"{Path(item.src_file).name}:{item.src_line_start}",
        }
        for item in items
    ]

    generated = []
    month = None
    if args.month:
        start, _end = parse_month(args.month)
        month = month_key(start)
        generated = [
            tx for tx in book.transactions if tx.meta.get("定期") and month_key(tx.date) == month
        ]

    if args.as_json:
        print(
            json.dumps(
                {
                    "模板": rows,
                    "月份": month,
                    "展开": [
                        {
                            "日期": tx.date.isoformat(),
                            "说明": tx.narration,
                            "金额": fmt_amount(tx.postings[0].units.number)
                            if tx.postings[0].units
                            else "",
                        }
                        for tx in generated
                    ],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    if not items:
        print(
            style(
                '账本里还没有定期交易模板（写法：`2026-01-01 recur "monthly" "房租" '
                "from 2026-01-01 to 2026-12-01` + 分录）",
                DIM,
            )
        )
        return 0

    print(
        render(
            ["周期", "说明", "起", "止", "下次", "分录", "来源"],
            [
                [row[c] for c in ("周期", "说明", "起", "止", "下次", "分录", "来源")]
                for row in rows
            ],
            aligns=["left", "left", "left", "left", "left", "right", "left"],
        )
    )
    if month:
        print()
        if generated:
            print(
                render(
                    ["日期", "说明", "金额"],
                    [
                        [
                            tx.date.isoformat(),
                            tx.narration,
                            fmt_amount(tx.postings[0].units.number) if tx.postings[0].units else "",
                        ]
                        for tx in generated
                    ],
                    aligns=["left", "left", "right"],
                )
            )
        else:
            print(style(f"{month} 没有展开出的交易", DIM))
    return 0
