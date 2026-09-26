from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

from knot.cli.ansi import GREEN, style
from knot.cli.commands import abort_on_errors
from knot.core.actions import EntryRequest, write_entry
from knot.core.aliases import AliasTable
from knot.core.lexer import is_account
from knot.core.loader import load_book
from knot.core.normalize import KnotError, normalize_text
from knot.core.writer import render_transaction


def add_parser(sub) -> None:
    p = sub.add_parser("add", aliases=["记", "a"], help="记一笔")
    p.add_argument("金额", nargs="?", metavar="金额")
    p.add_argument("科目", nargs="?", metavar="科目")
    p.add_argument("-f", "--from", dest="from_", metavar="科目", help="资金来自哪个科目")
    p.add_argument("-t", "--to", dest="to_", metavar="科目", help="资金去向哪个科目")
    p.add_argument("-d", "--date", dest="date", metavar="日期", help="交易日期，默认今天")
    p.add_argument("-n", "--note", dest="note", metavar="摘要", help="摘要")
    p.add_argument("--收款方", dest="payee", metavar="名称", help="收款方，同时沉淀分类规则")
    p.add_argument("--标签", dest="tags", action="append", metavar="标签", help="标签，可重复")
    p.set_defaults(func=run)


def _resolve(aliases: AliasTable, text: str, what: str) -> str:
    text = normalize_text(text).strip()
    resolution = aliases.resolve(text)
    if resolution.target:
        return resolution.target
    if resolution.candidates:
        if not sys.stdin.isatty():
            joined = "、".join(resolution.candidates)
            raise KnotError(f"{what}有多个候选，请写全名：{joined}")
        for i, candidate in enumerate(resolution.candidates, 1):
            print(f"  {i}. {candidate}")
        choice = input(f"请选择{what}编号：").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(resolution.candidates):
            return resolution.candidates[int(choice) - 1]
        raise KnotError(f"无效的{what}选择：{choice}")
    if is_account(text):
        return text
    raise KnotError(f"无法识别的{what}：{text}")


def _prompt(label: str, default: str | None = None) -> str:
    if not sys.stdin.isatty():
        raise KnotError(f"缺少参数：{label}")
    hint = f"（默认 {default}）" if default else ""
    value = input(f"{label}{hint}：").strip()
    return value or (default or "")


def run(args) -> int:
    ledger = Path(args.ledger)
    result, _book, diags = load_book(ledger, missing_ok=True)
    if abort_on_errors(diags):
        return 1

    amount_text = args.金额 or _prompt("金额")
    account_text = args.科目 or _prompt("科目")
    account = _resolve(result.aliases, account_text, "科目")

    root = account.split(":")[0]
    if root == "费用":
        sign = Decimal(1)
        raw_counterparty = args.from_ or result.options.default_asset
    elif root == "收入":
        sign = Decimal(-1)
        raw_counterparty = args.to_ or result.options.default_income
    elif args.to_ and not args.from_:
        sign = Decimal(-1)
        raw_counterparty = args.to_
    else:
        sign = Decimal(1)
        raw_counterparty = args.from_ or args.to_
    counterparty = (
        _resolve(result.aliases, raw_counterparty, "对手科目") if raw_counterparty else None
    )

    request = EntryRequest(
        amount=amount_text,
        account=account,
        from_account=counterparty,
        when=args.date,
        note=args.note or "",
        payee=args.payee,
        tags=tuple(args.tags or []),
        sign=sign,
    )
    entry = write_entry(
        request,
        ledger=ledger,
        aliases=result.aliases,
        options=result.options,
        rules=result.rules,
        files=result.files,
    )

    block = "".join(render_transaction(entry.transaction)).rstrip("\n")
    print(block)
    print(style(f"已记入 {entry.target}", GREEN))
    return 0
