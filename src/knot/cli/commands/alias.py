from __future__ import annotations

from pathlib import Path

from knot.cli.ansi import GREEN, YELLOW, style
from knot.core.aliases import COMMAND_ALIASES, is_complete_account, load_alias_file
from knot.core.normalize import KnotError
from knot.core.table import render

ALIAS_FILENAME = "别名.knot"
HEADER = "; 别名.knot\n; 格式：别名 = 目标\n; 目标可为完整科目名或命令关键字\n"


def add_parser(sub) -> None:
    p = sub.add_parser("alias", aliases=["别名"], help="别名管理")
    sp = p.add_subparsers(dest="alias_cmd", required=True)

    listing = sp.add_parser("列表", aliases=["list"], help="列出别名")
    listing.add_argument(
        "--全部", "--all", dest="all_aliases", action="store_true", help="同时列出内置别名"
    )
    listing.set_defaults(func=run_list)
    add = sp.add_parser("添加", aliases=["add"], help="添加别名")
    add.add_argument("别名", metavar="别名")
    add.add_argument("目标", metavar="目标", help="完整科目名或命令关键字")
    add.set_defaults(func=run_add)
    remove = sp.add_parser("删除", aliases=["remove", "del"], help="删除别名")
    remove.add_argument("别名", metavar="别名")
    remove.set_defaults(func=run_remove)
    test = sp.add_parser("测试", aliases=["test"], help="测试一个词会解析成什么（含拼音）")
    test.add_argument("词", metavar="词")
    test.set_defaults(func=run_test)

    p.set_defaults(func=run_list)


def _path(args) -> Path:
    return Path(args.ledger).parent / ALIAS_FILENAME


def _rewrite(path: Path, mapping: dict[str, str]) -> None:
    lines = [line for line in HEADER.strip("\n").split("\n")]
    lines.extend(f"{key} = {value}" for key, value in mapping.items())
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="")


def run_list(args) -> int:
    path = _path(args)
    mapping = load_alias_file(path) if path.exists() else {}
    if getattr(args, "all_aliases", False):
        from knot.core.aliases import AliasTable

        mapping = AliasTable(mapping).all()
    if not mapping:
        print(style(f"暂无用户别名（文件：{path}；加 --全部 可看内置别名）", YELLOW))
        return 0
    rows = [[key, value] for key, value in sorted(mapping.items())]
    print(render(["别名", "目标"], rows))
    return 0


def run_test(args) -> int:
    from knot.core.loader import load_book

    result, book, _diags = load_book(Path(args.ledger), missing_ok=True)
    word = args.词
    resolution = result.aliases.resolve(word, book.used_accounts())
    if resolution.target:
        print(style(f"{word} → {resolution.target}", GREEN))
        return 0
    if resolution.candidates:
        print(style(f"{word} 有多个候选：", YELLOW))
        for candidate in resolution.candidates:
            print(f"  {candidate}")
        return 0
    print(style(f"{word} 没有匹配到别名或科目（拼音检索：xianjin、zhaohang、fycy 这类）", YELLOW))
    return 0


def run_add(args) -> int:
    key = args.别名.strip()
    target = args.目标.strip()
    if not key or (" " in key):
        raise KnotError(f"别名不合法：{args.别名}")
    if target not in COMMAND_ALIASES and not is_complete_account(target):
        raise KnotError(f"目标应为完整科目名（根:子科目）或命令关键字：{target}")

    path = _path(args)
    mapping = load_alias_file(path) if path.exists() else {}
    mapping[key] = target
    _rewrite(path, mapping)
    print(style(f"已添加别名：{key} = {target}", GREEN))
    return 0


def run_remove(args) -> int:
    path = _path(args)
    mapping = load_alias_file(path) if path.exists() else {}
    if args.别名 not in mapping:
        raise KnotError(f"别名不存在：{args.别名}")
    del mapping[args.别名]
    _rewrite(path, mapping)
    print(style(f"已删除别名：{args.别名}", GREEN))
    return 0
