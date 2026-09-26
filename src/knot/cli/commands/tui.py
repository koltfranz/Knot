from __future__ import annotations

import sys
from pathlib import Path

from knot.tui import term
from knot.tui.app import run_tui


def add_parser(sub) -> None:
    p = sub.add_parser("tui", aliases=["界面"], help="终端三栏界面")
    p.set_defaults(func=run)


def run(args) -> int:
    ledger = Path(args.ledger)
    if not term.is_tty():
        print(
            "当前环境不是交互式终端，无法启动三栏界面；"
            "可改用 查 / 余 / 报 / 图 等命令，或在真实终端中运行。",
            file=sys.stderr,
        )
        return 2
    return run_tui(ledger)
