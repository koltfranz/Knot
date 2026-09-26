from __future__ import annotations

import sys

from knot.cli.ansi import DIM, style

MENU = [
    ("1", "记一笔", ["记"]),
    ("2", "查流水", ["查"]),
    ("3", "看余额", ["余", "--树"]),
    ("4", "校验账本", ["检查"]),
    ("5", "规范化全角/半角", ["规范"]),
    ("6", "浏览器界面（本地服务）", ["服务", "--打开浏览器"]),
    ("7", "终端界面（TUI）", ["界面"]),
    ("8", "初始化新账本", ["初始化"]),
    ("0", "退出", None),
]

_ACTIONS = {key: action for key, _label, action in MENU}


def add_parser(sub) -> None:
    p = sub.add_parser("menu", aliases=["菜单"], help="交互菜单（一键启动脚本使用）")
    p.set_defaults(func=run)


def _render() -> str:
    lines = ["", "结绳 Knot · 主菜单", "------------------"]
    lines.extend(f"  {key}. {label}" for key, label, _action in MENU)
    return "\n".join(lines)


def run(args) -> int:
    if not sys.stdin.isatty():
        print(_render())
        return 0

    from knot.cli.main import main as dispatch

    while True:
        print(_render())
        try:
            choice = input("请选择：").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if choice in ("0", "q", "quit", "退出"):
            return 0
        action = _ACTIONS.get(choice)
        if action is None:
            print(style("无效选择，请重新输入", DIM))
            continue
        try:
            code = dispatch(["--账本", args.ledger, *action])
        except KeyboardInterrupt:
            print()
            return 130
        if code:
            print(style(f"（退出码 {code}）", DIM))
