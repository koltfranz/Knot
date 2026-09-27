from __future__ import annotations

import argparse
import sys
from pathlib import Path

from knot.cli import ansi, completion
from knot.cli.ansi import RED, style
from knot.cli.commands import (
    add,
    alias,
    bal,
    budget,
    chart,
    check,
    create,
    demo,
    doctor,
    fmt,
    holdings,
    import_,
    init,
    menu,
    normalize,
    open_,
    reconcile,
    recur,
    report,
    serve,
    show,
    tui,
)
from knot.core.console import setup_console
from knot.core.normalize import KnotError
from knot.version import __version__

COMMANDS = (
    add,
    show,
    bal,
    report,
    chart,
    budget,
    recur,
    holdings,
    check,
    fmt,
    import_,
    reconcile,
    alias,
    normalize,
    init,
    create,
    open_,
    serve,
    tui,
    menu,
    demo,
    doctor,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="knot", description="结绳 Knot：纯文本复式记账")
    parser.add_argument(
        "--账本",
        "--ledger",
        dest="ledger",
        default="main.knot",
        help="主账本文件（默认 main.knot）",
    )
    parser.add_argument(
        "--补全",
        "--completion",
        dest="completion",
        choices=["bash", "zsh", "fish", "powershell", "pwsh"],
        help="输出 shell 补全脚本",
    )
    parser.add_argument("--version", action="version", version=f"knot {__version__}")
    sub = parser.add_subparsers(dest="cmd", title="命令")
    for module in COMMANDS:
        module.add_parser(sub)
    return parser


def main(argv: list[str] | None = None) -> int:
    setup_console()
    ansi.enable_vt()
    parser = build_parser()
    args = parser.parse_args(argv)

    if getattr(args, "completion", None):
        print(completion.generate(args.completion, parser))
        return 0
    if getattr(args, "cmd", None) is None:
        parser.print_help()
        return 2

    if getattr(args, "needs_ledger", False):
        ledger = Path(args.ledger)
        if not ledger.exists():
            print(
                f"{style('错误', RED)}：当前目录没有账本 {args.ledger}；"
                f"可用 `knot create 我的账本` 新建，或 `knot 示例` 复制示例账本，"
                f"或用 `--账本 路径` 指定",
                file=sys.stderr,
            )
            return 2

    try:
        return args.func(args) or 0
    except KnotError as exc:
        print(f"{style('错误', RED)}：{exc}", file=sys.stderr)
        return 2
    except FileNotFoundError as exc:
        print(f"{style('错误', RED)}：文件不存在：{exc.filename}", file=sys.stderr)
        return 2
    except BrokenPipeError:
        return 0
    except KeyboardInterrupt:
        print(file=sys.stderr)
        return 130
