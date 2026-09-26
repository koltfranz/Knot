from __future__ import annotations

import sys
from pathlib import Path

from knot.cli.ansi import GREEN, RED, style
from knot.core.diagnostic import count, render_all
from knot.core.loader import load_book


def add_parser(sub) -> None:
    p = sub.add_parser("check", aliases=["检查"], help="校验账本")
    p.add_argument("--静默", "--quiet", dest="quiet", action="store_true", help="只在出错时输出")
    p.set_defaults(func=run)


def run(args) -> int:
    _result, _book, diags = load_book(Path(args.ledger))
    errors = count(diags, "error")

    if diags and not args.quiet:
        print(render_all(diags), file=sys.stderr)

    summary = f"错误 {errors}，警告 {count(diags, 'warning')}，提示 {count(diags, 'hint')}"
    if errors:
        print(style(summary, RED), file=sys.stderr)
        return 1

    if not args.quiet:
        print(summary, file=sys.stderr)
    print(style("账本正常", GREEN))
    return 0
