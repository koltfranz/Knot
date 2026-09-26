from __future__ import annotations

import json
from pathlib import Path

from knot.cli.ansi import DIM, YELLOW, style
from knot.cli.commands import abort_on_errors
from knot.core.amount import fmt_amount
from knot.core.inventory import (
    METHOD_AVERAGE,
    METHOD_FIFO,
    build_positions,
    holdings_value,
    net_worth_in,
)
from knot.core.loader import load_book
from knot.core.table import render


def add_parser(sub) -> None:
    p = sub.add_parser("holdings", aliases=["持仓"], help="投资持仓、成本基础与盈亏")
    p.add_argument(
        "--方法",
        dest="method",
        choices=["fifo", "average", "先进先出", "平均"],
        default="fifo",
        help="成本基础：fifo（默认）或 average",
    )
    p.add_argument(
        "--折算",
        dest="convert_to",
        metavar="币种",
        nargs="?",
        const="",
        help="把净资产按报价折算到该币种（默认记账币种）",
    )
    p.add_argument("--json", dest="as_json", action="store_true")
    p.set_defaults(func=run)


def _method(text: str) -> str:
    return METHOD_AVERAGE if text in ("average", "平均") else METHOD_FIFO


def run(args) -> int:
    _result, book, diags = load_book(Path(args.ledger))
    if abort_on_errors(diags):
        return 1

    method = _method(args.method)
    positions = build_positions(book, method=method)
    valuation = holdings_value(book)
    operated = net_worth_in(book, args.convert_to or None)
    currency = book.options.operating_currency

    if args.as_json:
        print(
            json.dumps(
                {
                    "方法": method,
                    "持仓": [
                        {
                            "科目": item.account,
                            "商品": item.commodity,
                            "数量": str(item.units),
                            "成本": fmt_amount(item.cost_total),
                            "单位成本": str(item.unit_cost),
                            "最新价": str(item.market_price)
                            if item.market_price is not None
                            else None,
                            "市值": fmt_amount(item.market_value)
                            if item.market_value is not None
                            else None,
                            "未实现盈亏": fmt_amount(item.unrealized)
                            if item.unrealized is not None
                            else None,
                            "已实现盈亏": fmt_amount(item.realized),
                            "成本币种": item.cost_currency,
                        }
                        for item in positions
                    ],
                    "缺报价": valuation["缺报价"],
                    "净资产": {
                        "币种": operated["币种"],
                        "折算后": fmt_amount(operated["折算后"]),
                        "缺报价": {
                            key: fmt_amount(value) for key, value in operated["缺报价"].items()
                        },
                    },
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    if not positions:
        print(style("没有持仓（带成本的分录写法：`1000 FUND {3.8500 CNY}`）", DIM))
    else:
        table = []
        for item in positions:
            table.append(
                [
                    item.account,
                    item.commodity,
                    str(item.units),
                    fmt_amount(item.cost_total),
                    str(item.unit_cost),
                    str(item.market_price) if item.market_price is not None else "—",
                    fmt_amount(item.market_value) if item.market_value is not None else "—",
                    fmt_amount(item.unrealized) if item.unrealized is not None else "—",
                    fmt_amount(item.realized) if item.realized else "",
                ]
            )
        print(
            render(
                ["科目", "商品", "数量", "成本", "单位成本", "最新价", "市值", "未实现", "已实现"],
                table,
                aligns=[
                    "left",
                    "left",
                    "right",
                    "right",
                    "right",
                    "right",
                    "right",
                    "right",
                    "right",
                ],
            )
        )

    if valuation["缺报价"]:
        print(style(f"缺报价（按成本计入）：{'、'.join(valuation['缺报价'])}", YELLOW))

    print(
        f"净资产折算：{fmt_amount(operated['折算后'])} {operated['币种']}"
        + (f"（另有缺报价：{'、'.join(operated['缺报价'])}）" if operated["缺报价"] else "")
        + f"　成本币种：{currency} 口径"
    )
    return 0
