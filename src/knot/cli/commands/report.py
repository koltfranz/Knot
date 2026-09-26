from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from knot.cli.commands import abort_on_errors
from knot.core.amount import fmt_amount
from knot.core.date_cn import parse_date, parse_month
from knot.core.loader import load_book
from knot.core.normalize import KnotError
from knot.core.report import (
    balance_over_time,
    category_trend,
    expense_by_category,
    monthly_flow,
    net_worth_trend,
    render_monthly_flow,
    render_pairs,
    render_summary,
    render_trend,
)

KINDS = ("概况", "收支", "净资产", "分类", "科目")

ALIASES = {
    "summary": "概况",
    "income": "收支",
    "expense": "收支",
    "networth": "净资产",
    "net": "净资产",
    "category": "分类",
    "account": "科目",
}


def add_parser(sub) -> None:
    p = sub.add_parser("report", aliases=["报", "r"], help="报表")
    p.add_argument(
        "类型", nargs="?", default="概况", metavar="类型", help="概况 / 收支 / 净资产 / 分类 / 科目"
    )
    p.add_argument("--月", "--month", dest="month", metavar="月份")
    p.add_argument("--年", "--year", dest="year", metavar="年份")
    p.add_argument("--从", "--from", dest="date_from", metavar="日期")
    p.add_argument("--到", "--to", dest="date_to", metavar="日期")
    p.add_argument("--科目", dest="account", metavar="科目", help="科目报表的目标科目")
    p.add_argument("--深度", dest="depth", type=int, default=2, metavar="N", help="分类聚合层级")
    p.add_argument("--前", dest="top", type=int, default=10, metavar="N", help="只显示前 N 项")
    p.add_argument("--json", dest="as_json", action="store_true")
    p.set_defaults(func=run)


def _range(args) -> tuple[date | None, date | None]:
    if args.month:
        return parse_month(args.month)
    if args.year:
        return parse_month(f"{args.year}-1")[0], parse_month(f"{args.year}-12")[1]
    start = parse_date(args.date_from) if args.date_from else None
    end = parse_date(args.date_to) if args.date_to else None
    return start, end


def _kind(raw: str) -> str:
    if raw in KINDS:
        return raw
    canonical = ALIASES.get(raw.lower())
    if canonical:
        return canonical
    raise KnotError(f"未知报表类型：{raw}（可选 {' / '.join(KINDS)}）")


def _jsonable(value):
    from decimal import Decimal

    if isinstance(value, Decimal):
        return fmt_amount(value)
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    return value


def run(args) -> int:
    result, book, diags = load_book(Path(args.ledger))
    if abort_on_errors(diags):
        return 1

    kind = _kind(args.类型)
    start, end = _range(args)

    if kind == "概况":
        payload = book.summary()
        if args.as_json:
            print(json.dumps(_jsonable(payload), ensure_ascii=False, indent=2))
        else:
            print(render_summary(payload))
        return 0

    if kind == "收支":
        rows = monthly_flow(book, start, end)
        if args.as_json:
            print(json.dumps(_jsonable(rows), ensure_ascii=False, indent=2))
        else:
            print(render_monthly_flow(rows))
        return 0

    if kind == "净资产":
        rows = net_worth_trend(book, start, end)
        currency = book.options.operating_currency
        display = [{"月份": row["月份"], "净资产": row.get(currency, 0)} for row in rows]
        if args.as_json:
            print(json.dumps(_jsonable(rows), ensure_ascii=False, indent=2))
        else:
            print(render_trend(display, "净资产", "净资产"))
        return 0

    if kind == "分类":
        rows = expense_by_category(book, start, end, depth=args.depth, top=args.top)
        if args.as_json:
            print(
                json.dumps(
                    {name: fmt_amount(value) for name, value in rows}, ensure_ascii=False, indent=2
                )
            )
        else:
            print(render_pairs(rows, "科目", "支出"))
        return 0

    account = args.account
    if not account:
        raise KnotError("科目报表需要 --科目 指定科目")
    resolution = result.aliases.resolve(account)
    account = resolution.target or account

    if args.as_json:
        payload = {
            "科目": account,
            "余额": _jsonable(balance_over_time(book, account, start, end)),
            "流水": _jsonable(category_trend(book, account, start, end)),
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    print(f"科目：{account}")
    print(render_trend(balance_over_time(book, account, start, end), "余额", "月末余额"))
    print()
    print(render_trend(category_trend(book, account, start, end), "金额", "当月发生"))
    return 0
