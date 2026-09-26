from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

from knot.cli.ansi import GREEN, style
from knot.cli.commands import abort_on_errors
from knot.core.aliases import AliasTable
from knot.core.date_cn import parse_date
from knot.core.lexer import is_account
from knot.core.loader import load_book
from knot.core.model import Amount, Flag, Posting, Transaction
from knot.core.normalize import KnotError, normalize_text
from knot.core.number_cn import parse_amount
from knot.core.writer import insert_transaction, render_transaction


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


def _target_file(ledger: Path, year: int, files: list[Path]) -> Path:
    name = f"{year}.knot"
    for file in files:
        if file.name == name:
            return file
    return ledger


def run(args) -> int:
    ledger = Path(args.ledger)
    result, _book, diags = load_book(ledger, missing_ok=True)
    if abort_on_errors(diags):
        return 1

    amount_text = args.金额
    account_text = args.科目
    if not amount_text:
        amount_text = _prompt("金额")
    if not account_text:
        account_text = _prompt("科目")

    amount = parse_amount(amount_text)
    account = _resolve(result.aliases, account_text, "科目")
    when = parse_date(args.date or "今天")

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
    elif args.from_:
        sign = Decimal(1)
        raw_counterparty = args.from_
    else:
        raw_counterparty = None
        sign = Decimal(1)
    if raw_counterparty is None:
        raise KnotError("请用 -f/--from 或 -t/--to 指定对手科目")
    counterparty = _resolve(result.aliases, raw_counterparty, "对手科目")

    posting = Posting(
        account=account,
        units=Amount(sign * amount, result.options.operating_currency),
        counterparty=counterparty,
    )
    tx = Transaction(
        date=when,
        flag=Flag.OK,
        payee=args.payee,
        narration=normalize_text(args.note or ""),
        postings=[posting],
        tags=frozenset(normalize_text(t) for t in (args.tags or [])),
    )

    target = _target_file(ledger, when.year, result.files)
    insert_transaction(target, tx)

    if args.payee and result.rules.path is not None:
        result.rules.learn(args.payee, account)

    block = "".join(render_transaction(tx)).rstrip("\n")
    print(block)
    print(style(f"已记入 {target}", GREEN))
    return 0
