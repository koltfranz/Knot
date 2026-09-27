from __future__ import annotations

import sys
from pathlib import Path

from knot.cli.ansi import DIM, YELLOW, style
from knot.cli.commands import abort_on_errors
from knot.core.loader import load_book
from knot.core.normalize import KnotError
from knot.tui import term


def add_parser(sub) -> None:
    p = sub.add_parser("open", aliases=["打开", "开"], help="打开账本（默认进入终端界面）")
    p.add_argument(
        "名字",
        nargs="?",
        default=None,
        metavar="名字",
        help="账本目录名或 .knot 文件；省略则用 --账本",
    )
    p.add_argument(
        "--网页", "--web", dest="web", action="store_true", help="改用浏览器界面（本地服务）"
    )
    p.set_defaults(func=run)


def resolve_ledger(name: str | None, default: str) -> Path:
    """名字 → 账本文件：文件 → 名字/main.knot → 名字.knot。"""
    if not name:
        path = Path(default)
        if path.is_file():
            return path
        raise KnotError(
            f"当前目录没有账本文件 {default}；"
            "可用 `knot create 我的账本` 新建，或指定名字：knot open 我的账本"
        )
    candidate = Path(name).expanduser()
    paths = [candidate]
    if candidate.suffix != ".knot":
        paths.append(candidate.with_suffix(".knot"))
    paths.append(candidate / "main.knot")
    for path in paths:
        if path.is_file():
            return path
    if candidate.is_dir():
        raise KnotError(f"{candidate} 里没有 main.knot；可用 `knot create {candidate}` 生成骨架")
    raise KnotError(f"未找到账本：{name}；可用 `knot create {name}` 新建")


def run(args) -> int:
    ledger = resolve_ledger(args.名字, args.ledger)
    _result, book, diags = load_book(ledger, missing_ok=True)
    if abort_on_errors(diags):
        print(style(f"提示：knot --账本 {ledger} 检查 可查看完整诊断", YELLOW), file=sys.stderr)
        return 1

    if args.web:
        from knot.cli.main import main as dispatch

        return dispatch(["--账本", str(ledger), "服务", "--打开浏览器"])

    if not term.is_tty():
        from knot.cli.commands.report import overview_text

        print(overview_text(book))
        print(style(f"提示：当前不是交互式终端，已输出概况；账本：{ledger}", DIM))
        return 0

    from knot.tui.app import run_tui

    return run_tui(ledger)
