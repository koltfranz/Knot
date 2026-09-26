from __future__ import annotations

from pathlib import Path

from knot.cli.ansi import GREEN, YELLOW, style
from knot.core.fmt import format_file
from knot.core.loader import Loader


def add_parser(sub) -> None:
    p = sub.add_parser("fmt", aliases=["整理"], help="格式化对齐账本")
    p.add_argument(
        "--检查",
        "--check",
        dest="check_only",
        action="store_true",
        help="只检查是否需要整理，不写入",
    )
    p.set_defaults(func=run)


def run(args) -> int:
    result = Loader().load(Path(args.ledger))
    changed: list[Path] = []
    for file in result.files:
        if file.suffix != ".knot":
            continue
        if format_file(file):
            changed.append(file)

    if args.check_only:
        if changed:
            for file in changed:
                print(style(f"需要整理：{file}", YELLOW))
            return 1
        print(style("无需整理", GREEN))
        return 0

    if not changed:
        print(style("无需整理", GREEN))
        return 0
    for file in changed:
        print(style(f"已整理：{file}", GREEN))
    return 0
