from __future__ import annotations

import json
from pathlib import Path

from knot.cli.ansi import DIM, GREEN, RED, YELLOW, style
from knot.cli.commands import abort_on_errors
from knot.core.amount import fmt_amount
from knot.core.budget import rows, summary
from knot.core.date_cn import parse_month
from knot.core.loader import load_book
from knot.core.table import render


def add_parser(sub) -> None:
    p = sub.add_parser("budget", aliases=["预算"], help="预算与进度")
    p.add_argument("--月", "--month", dest="month", metavar="月份", help="如 2026-09 或 本月")
    p.add_argument("--json", dest="as_json", action="store_true")
    p.set_defaults(func=run)


def _month(text: str | None) -> str | None:
    if not text:
        return None
    start, _end = parse_month(text)
    return f"{start.year:04d}-{start.month:02d}"


def run(args) -> int:
    _result, book, diags = load_book(Path(args.ledger))
    if abort_on_errors(diags):
        return 1

    month = _month(args.month)
    items = rows(book, month)
    if args.as_json:
        print(
            json.dumps(
                {
                    "进度": [
                        {
                            **item,
                            "预算": fmt_amount(item["预算"]),
                            "实际": fmt_amount(item["实际"]),
                            "剩余": fmt_amount(item["剩余"]),
                            "进度": f"{item['进度'] * 100:.1f}%",
                        }
                        for item in items
                    ],
                    "合计": {
                        key: (fmt_amount(value) if hasattr(value, "quantize") else value)
                        for key, value in summary(book, month).items()
                    },
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    if not items:
        print(
            style(
                "账本里还没有预算（在年份文件写 "
                "`2026-01-01 budget monthly 费用:餐饮 2000.00 CNY`）",
                DIM,
            )
        )
        return 0

    table = [
        [
            item["科目"],
            item["月份"],
            fmt_amount(item["预算"]),
            fmt_amount(item["实际"]),
            fmt_amount(item["剩余"]),
            f"{item['进度'] * 100:.1f}%",
        ]
        for item in items
    ]
    print(
        render(
            ["科目", "月份", "预算", "实际", "剩余", "进度"],
            table,
            aligns=["left", "left", "right", "right", "right", "right"],
        )
    )
    total = summary(book, month)
    print(
        style(
            f"合计：预算 {fmt_amount(total['预算合计'])} · 实际 {fmt_amount(total['实际合计'])} · "
            f"剩余 {fmt_amount(total['剩余合计'])}",
            GREEN if not total["超支科目"] else YELLOW,
        )
    )
    for account in total["超支科目"]:
        print(style(f"超支：{account}", RED))
    return 0
