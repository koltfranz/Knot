from __future__ import annotations

import json
from pathlib import Path

from knot.cli.ansi import GREEN, YELLOW, style
from knot.cli.commands import abort_on_errors
from knot.core.actions import resolve_account
from knot.core.amount import fmt_amount
from knot.core.date_cn import parse_date
from knot.core.loader import load_book
from knot.core.normalize import KnotError
from knot.core.number_cn import parse_amount
from knot.core.reconcile import (
    balance_assertion,
    mark_cleared,
    reconcile,
    render_report,
    write_assertion,
)


def add_parser(sub) -> None:
    p = sub.add_parser("reconcile", aliases=["对账"], help="对账向导")
    p.add_argument("科目", metavar="科目", help="如 资产:银行:招行")
    p.add_argument("--余额", dest="statement", metavar="金额", help="账单上的期末余额")
    p.add_argument("--日期", dest="date", metavar="日期", default=None)
    p.add_argument(
        "--标记", dest="mark", action="store_true", help="把待对账交易标记为 P（已对账）"
    )
    p.add_argument(
        "--断言",
        dest="assertion",
        action="store_true",
        help="把账单余额写成 balance 断言（可用 检查 复验）",
    )
    p.add_argument("--条数", dest="limit", type=int, default=20, metavar="N")
    p.add_argument("--json", dest="as_json", action="store_true")
    p.set_defaults(func=run)


def run(args) -> int:
    ledger = Path(args.ledger)
    result, book, diags = load_book(ledger)
    if abort_on_errors(diags):
        return 1

    account = resolve_account(result.aliases, args.科目, "科目", book.used_accounts())
    as_of = parse_date(args.date) if args.date else None
    statement = parse_amount(args.statement) if args.statement else None

    report = reconcile(book, account, statement, as_of, limit=args.limit)

    if args.as_json:
        print(
            json.dumps(
                {
                    "科目": report.account,
                    "截止": report.as_of.isoformat(),
                    "账本余额": fmt_amount(report.ledger_balance),
                    "账单余额": fmt_amount(statement) if statement is not None else None,
                    "差额": fmt_amount(report.difference)
                    if report.difference is not None
                    else None,
                    "已对账": report.cleared,
                    "待对账": [
                        {
                            "日期": tx.date.isoformat(),
                            "摘要": tx.payee or tx.narration,
                            "来源": f"{tx.src_file}:{tx.src_line_start}",
                        }
                        for tx in report.pending
                    ],
                    "建议": report.suggestion,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        print(render_report(report, book.options.operating_currency))

    if args.assertion:
        if statement is None:
            raise KnotError("--断言 需要同时给出 --余额")
        assertion = balance_assertion(book, account, statement, report.as_of)
        target = write_assertion(ledger, assertion, result.files)
        print(style(f"已写入余额断言：{target}", GREEN))

    if args.mark:
        if not report.pending:
            print(style("没有待对账交易", YELLOW))
        else:
            count = mark_cleared(report.pending)
            print(style(f"已标记 {count} 笔为 P（已对账）", GREEN))

    if statement is not None and not report.balanced:
        return 1
    return 0
