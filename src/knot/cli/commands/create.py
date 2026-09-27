from __future__ import annotations

from pathlib import Path

from knot.cli.ansi import DIM, style
from knot.cli.commands.init import add_scaffold_options, run_scaffold
from knot.core.normalize import KnotError

SUFFIX = ".knot"


def add_parser(sub) -> None:
    p = sub.add_parser("create", aliases=["新建", "创建"], help="新建命名账本（目录 + 默认内容）")
    p.add_argument("名字", metavar="名字", help="账本目录名，如 我的账本")
    add_scaffold_options(p)
    p.set_defaults(func=run)


def target_directory(name: str) -> Path:
    """名字 → 账本目录；`我的账本.knot` 视作目录名 `我的账本`。"""
    directory = Path(name.strip())
    if not directory.name:
        raise KnotError(f"账本名字不合法：{name}")
    if directory.suffix == SUFFIX:
        directory = directory.with_suffix("")
    return directory


def run(args) -> int:
    if not args.名字.strip():
        raise KnotError("请提供账本名字：knot create 我的账本")
    directory = target_directory(args.名字)
    if args.名字.strip() != str(directory):
        print(style(f"提示：create 生成的是账本目录，已按 {directory} 处理", DIM))
    shown = f'"{directory}"' if " " in str(directory) else str(directory)
    return run_scaffold(args, directory, hint=f"knot open {shown}")
