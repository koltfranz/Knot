from __future__ import annotations

import argparse
import sys

from knot.cli import ansi, completion
from knot.cli.ansi import RED, style
from knot.cli.commands import add, alias, bal, check, fmt, show
from knot.core.console import setup_console
from knot.core.normalize import KnotError
from knot.version import __version__

COMMANDS = (add, show, bal, check, fmt, alias)


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
        choices=["bash", "zsh", "fish"],
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
