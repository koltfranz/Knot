from __future__ import annotations

import json
from pathlib import Path

from knot.cli.ansi import DIM, style
from knot.cli.commands import abort_on_errors
from knot.core.amount import fmt_amount, is_zero
from knot.core.loader import load_book
from knot.core.table import render
from knot.core.width import pad, str_width


def add_parser(sub) -> None:
    p = sub.add_parser("bal", aliases=["余", "b"], help="科目余额")
    p.add_argument("科目", nargs="?", metavar="科目", help="限定科目及其子科目")
    p.add_argument("--树", "--tree", dest="tree", action="store_true", help="树形展示")
    p.add_argument("--深度", "--depth", dest="depth", type=int, metavar="N", help="树形最大深度")
    p.add_argument("--json", dest="as_json", action="store_true", help="输出结构化 JSON")
    p.set_defaults(func=run)


def _select_names(book, account: str | None) -> list[str]:
    names = book.used_accounts()
    if account:
        names = [n for n in names if n == account or n.startswith(account + ":")]
    return names


def _balance_text(book, name: str, include_children: bool) -> tuple[str, bool]:
    totals = book.balance_of(name, include_children=include_children)
    parts = [
        f"{fmt_amount(value)} {currency}"
        for currency, value in sorted(totals.items())
        if not is_zero(value)
    ]
    return "，".join(parts), bool(parts)


def _tree(book, names: list[str], account: str | None, depth: int | None) -> list[list[str]]:
    prefixes: set[str] = set()
    for name in names:
        parts = name.split(":")
        for i in range(1, len(parts) + 1):
            prefixes.add(":".join(parts[:i]))

    rows: list[list[str]] = []
    for node in sorted(prefixes):
        if account and not (node == account or node.startswith(account + ":")):
            continue
        depth_now = node.count(":")
        if depth is not None and depth_now + 1 > depth:
            continue
        label = node.split(":")[-1]
        text, has = _balance_text(book, node, include_children=True)
        if not has:
            continue
        rows.append(["  " * depth_now + label, text])
    return rows


def run(args) -> int:
    result, book, diags = load_book(Path(args.ledger))
    if abort_on_errors(diags):
        return 1
    account = args.科目
    if account:
        resolution = result.aliases.resolve(account)
        account = resolution.target or account

    names = _select_names(book, account)

    if args.as_json:
        payload = {}
        for name in names:
            totals = book.balance_of(name, include_children=False)
            payload[name] = {
                currency: fmt_amount(value)
                for currency, value in sorted(totals.items())
                if not is_zero(value)
            }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    if args.tree:
        rows = _tree(book, names, account, args.depth)
        if not rows:
            print(style("没有余额", DIM))
            return 0
        width = max(str_width(row[0]) for row in rows)
        for label, text in rows:
            print(f"{pad(label, width)}  {text}")
        return 0

    rows = []
    for name in names:
        text, has = _balance_text(book, name, include_children=False)
        if has:
            rows.append([name, text])
    if not rows:
        print(style("没有余额", DIM))
        return 0
    print(render(["科目", "余额"], rows, aligns=["left", "right"]))
    return 0
