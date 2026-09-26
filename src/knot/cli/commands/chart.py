from __future__ import annotations

import json
from pathlib import Path

from knot.cli.commands import abort_on_errors
from knot.core.chart import (
    KIND_BAR,
    KIND_HEATMAP,
    KIND_LINE,
    KIND_PIE,
    KIND_TREEMAP,
    ChartSpec,
    render_svg,
    spec_budget_gauge,
    spec_calendar_heatmap,
    spec_category_treemap,
    spec_expense_pie,
    spec_monthly_flow,
    spec_net_worth,
)
from knot.core.date_cn import parse_date, parse_month
from knot.core.loader import load_book
from knot.core.normalize import KnotError

KINDS = {
    "柱": KIND_BAR,
    "bar": KIND_BAR,
    "线": KIND_LINE,
    "折线": KIND_LINE,
    "line": KIND_LINE,
    "饼": KIND_PIE,
    "pie": KIND_PIE,
    "树": KIND_TREEMAP,
    "treemap": KIND_TREEMAP,
    "热力": KIND_HEATMAP,
    "日历": KIND_HEATMAP,
    "heatmap": KIND_HEATMAP,
}

TOPICS = ("支出", "收入", "净资产", "分类", "日历", "预算")


def add_parser(sub) -> None:
    p = sub.add_parser("chart", aliases=["图", "c"], help="生成图表（SVG）")
    p.add_argument(
        "主题", nargs="?", default="支出", metavar="主题", help="支出 / 净资产 / 分类 / 日历"
    )
    p.add_argument("--类型", "--type", dest="kind", metavar="类型", help="柱 / 线 / 饼 / 树 / 热力")
    p.add_argument("--按", dest="by", default="分类", metavar="分类|科目")
    p.add_argument("--月", "--month", dest="month", metavar="月份")
    p.add_argument("--年", "--year", dest="year", metavar="年份")
    p.add_argument("--从", "--from", dest="date_from", metavar="日期")
    p.add_argument("--到", "--to", dest="date_to", metavar="日期")
    p.add_argument("--前", dest="top", type=int, default=8, metavar="N")
    p.add_argument(
        "-o", "--输出", dest="output", metavar="文件.svg", help="写入文件，默认输出到标准输出"
    )
    p.add_argument("--json", dest="as_json", action="store_true", help="输出 ChartSpec JSON")
    p.set_defaults(func=run)


def _range(args):
    if args.month:
        return parse_month(args.month)
    if args.year:
        return parse_month(f"{args.year}-1")[0], parse_month(f"{args.year}-12")[1]
    start = parse_date(args.date_from) if args.date_from else None
    end = parse_date(args.date_to) if args.date_to else None
    return start, end


def _build(args, book, start, end) -> ChartSpec:
    topic = args.主题
    kind = KINDS.get(args.kind.lower()) if args.kind else None

    if topic in ("净资产", "networth"):
        return spec_net_worth(book, start, end)
    if topic in ("收入", "income"):
        return spec_monthly_flow(book, start, end)
    if topic in ("日历", "热力", "calendar"):
        year = None
        if args.year:
            year = int(args.year)
        elif start or end:
            year = (start or end).year
        if year is None:
            years = sorted({tx.date.year for tx in book.transactions})
            if not years:
                raise KnotError("账本中没有交易")
            year = years[-1]
        return spec_calendar_heatmap(book, year)
    if topic in ("预算", "budget"):
        return spec_budget_gauge(book, args.month, top=args.top)
    if topic in ("分类", "category"):
        if kind == KIND_TREEMAP:
            return spec_category_treemap(book, start, end, top=args.top)
        if kind == KIND_BAR:
            spec = spec_expense_pie(book, start, end, top=args.top)
            spec.kind = KIND_BAR
            return spec
        return spec_expense_pie(book, start, end, top=args.top)
    if topic in ("支出", "expense"):
        if kind == KIND_PIE:
            return spec_expense_pie(book, start, end, top=args.top)
        if kind == KIND_TREEMAP:
            return spec_category_treemap(book, start, end, top=args.top)
        return spec_monthly_flow(book, start, end)
    raise KnotError(f"未知图表主题：{topic}")


def run(args) -> int:
    _result, book, diags = load_book(Path(args.ledger))
    if abort_on_errors(diags):
        return 1

    start, end = _range(args)
    spec = _build(args, book, start, end)

    if args.as_json:
        print(json.dumps(spec.to_json(), ensure_ascii=False, indent=2))
        return 0

    svg = render_svg(spec)
    if args.output:
        path = Path(args.output)
        path.write_text(svg, encoding="utf-8", newline="")
        print(f"已生成图表：{path}（{spec.kind} · {spec.title}）")
    else:
        print(svg)
    return 0
