from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

from knot.cli.ansi import GREEN, YELLOW, style
from knot.cli.commands import abort_on_errors
from knot.core.diagnostic import count
from knot.core.keywords import ZH
from knot.core.loader import load_book
from knot.core.normalize import KnotError, normalize_text
from knot.core.scaffold import ScaffoldOptions, create_ledger

LANGUAGE_CHOICES = {"zh": ZH, "中文": ZH, "en": "en", "英文": "en"}


def add_parser(sub) -> None:
    p = sub.add_parser("init", aliases=["初始化", "新建"], help="生成账本骨架")
    p.add_argument("目录", nargs="?", default=".", metavar="目录", help="账本目录，默认当前目录")
    p.add_argument("--年份", dest="year", type=int, metavar="年", help="年份文件，默认今年")
    p.add_argument("--币种", dest="currency", default="CNY", metavar="币种")
    p.add_argument("--默认资产", dest="default_asset", default="资产:现金", metavar="科目")
    p.add_argument("--默认收入", dest="default_income", default="收入:其他", metavar="科目")
    p.add_argument(
        "--语言", dest="language", default="zh", metavar="zh|en", help="关键字语言：zh（默认）或 en"
    )
    p.add_argument("--覆盖", dest="overwrite", action="store_true", help="已存在的文件也重写")
    p.add_argument(
        "--非交互", dest="non_interactive", action="store_true", help="不提问，全部取默认值"
    )
    p.set_defaults(func=run)


def _prompt(label: str, default: str) -> str:
    if not sys.stdin.isatty():
        return default
    value = input(f"{label}（默认 {default}）：").strip()
    return value or default


def run(args) -> int:
    language = LANGUAGE_CHOICES.get(normalize_text(args.language).lower())
    if language is None:
        raise KnotError(f"未知语言：{args.language}（可选 zh / en）")

    directory = Path(args.目录)
    currency = args.currency
    if not args.non_interactive:
        directory = Path(_prompt("账本目录", str(directory)))
        currency = _prompt("记账币种", currency)
        language = LANGUAGE_CHOICES.get(
            normalize_text(_prompt("关键字语言（zh/en）", language)).lower(), language
        )

    options = ScaffoldOptions(
        directory=directory,
        year=args.year or date.today().year,
        currency=currency,
        default_asset=args.default_asset,
        default_income=args.default_income,
        language=language,
        overwrite=args.overwrite,
    )
    result = create_ledger(options)

    for path in result.created:
        print(style(f"已生成：{path}", GREEN))
    for path in result.skipped:
        print(style(f"已存在，跳过：{path}（加 --覆盖 可重写）", YELLOW))
    if not result.created and not result.skipped:
        raise KnotError("没有需要生成的文件")

    main_knot = directory / "main.knot"
    if main_knot.exists():
        _result, _book, diags = load_book(main_knot, missing_ok=True)
        if abort_on_errors(diags):
            return 1
        print(
            style(
                f"账本就绪：错误 {count(diags, 'error')}，"
                f"警告 {count(diags, 'warning')}，提示 {count(diags, 'hint')}",
                GREEN,
            )
        )
        print(f"下一步：knot --账本 {main_knot} 记 38 餐饮 -f 现金 -n 午饭")
    return 0
