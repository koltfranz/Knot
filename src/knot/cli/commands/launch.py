from __future__ import annotations

from datetime import date
from pathlib import Path

from knot.cli import entry
from knot.cli.ansi import DIM, GREEN, style
from knot.core.normalize import KnotError
from knot.core.scaffold import ScaffoldOptions, create_ledger

DEFAULT_HOME_NAME = "结绳账本"
INTERFACES = {"浏览器": "browser", "终端": "tui", "示例": "demo"}


def add_parser(sub) -> None:
    p = sub.add_parser("launch", aliases=["入口", "启动"], help="桌面入口：选择窗口 → 打开界面")
    p.add_argument(
        "--界面",
        dest="interface",
        choices=list(INTERFACES),
        metavar="浏览器|终端|示例",
        help="跳过选择窗口，直接打开指定界面",
    )
    p.add_argument(
        "--账本目录",
        dest="home",
        metavar="目录",
        help=f"账本主页，默认 ~/{DEFAULT_HOME_NAME}（也可用环境变量 KNOT_HOME）",
    )
    p.add_argument(
        "--超时",
        dest="timeout",
        type=float,
        default=10.0,
        metavar="秒",
        help="选择窗口等待秒数，超时按浏览器界面继续（默认 10）",
    )
    p.set_defaults(func=run, needs_ledger=False)


def ledger_home(explicit: str | None) -> Path:
    if explicit:
        return Path(explicit).expanduser()
    from_env = entry.home_from_env()
    if from_env is not None:
        return from_env
    return Path.home() / DEFAULT_HOME_NAME


def ensure_ledger(home: Path) -> Path:
    """账本主页没有账本时自动生成骨架：入口必须开箱可用。"""
    main = home / "main.knot"
    if main.exists():
        return main
    result = create_ledger(ScaffoldOptions(directory=home, year=date.today().year))
    for path in result.created:
        print(style(f"已生成：{path}", GREEN))
    print(style("账本就绪：可把年份文件里的注释示例改一改，直接用起来", DIM))
    return main


def ensure_demo(home: Path) -> Path:
    from knot.cli.commands.demo import DEMO_NAME, copy_demo

    target = home / DEMO_NAME
    created, _skipped = copy_demo(target, overwrite=False)
    if created:
        print(style(f"示例账本已复制到：{target}", GREEN))
    return target / "main.knot"


def _in_terminal() -> bool:
    """无控制台环境（pythonw）下 sys.stdin/stdout 为 None，必须安全判空。"""
    return entry.in_terminal()


def open_tui(ledger: Path) -> int:
    """打开终端界面：已在终端则直接进入，否则在新窗口拉起。"""
    from knot.cli.commands.open_ import launch

    if _in_terminal():
        return launch(ledger)
    if entry.spawn_tui(entry.console_executable(), ledger):
        print(style("已在新窗口打开终端界面", GREEN))
        return 0
    raise KnotError("当前环境无法打开新窗口；请在终端里运行：knot 打开 我的账本")


def open_browser(ledger: Path) -> int:
    """打开浏览器界面：已在终端则本进程提供服务，否则在新窗口拉起。"""
    from knot.cli.main import main as dispatch

    command = ["--账本", str(ledger), "服务", "--打开浏览器"]
    if _in_terminal():
        return dispatch(command)
    if entry.spawn_browser(entry.console_executable(), ledger):
        print(style("已在新窗口启动本地服务，浏览器即将打开", GREEN))
        return 0
    return dispatch(command)


def run(args) -> int:
    try:
        return _run(args)
    except Exception as exc:  # 桌面入口必须把失败告诉用户，而不是静默退出
        entry.report_error(f"{type(exc).__name__}: {exc}")
        return 1


def _run(args) -> int:
    choice = INTERFACES.get(args.interface) if args.interface else None
    if choice is None:
        choice = entry.choose(timeout=args.timeout)
    if choice in ("", "quit"):
        return 0

    home = ledger_home(args.home)
    if choice == "demo":
        ledger = ensure_demo(home)
        print(style(f"示例账本：{ledger}", DIM))
        return open_browser(ledger)

    ledger = ensure_ledger(home)
    print(style(f"账本：{ledger}", DIM))
    if choice == "tui":
        return open_tui(ledger)
    return open_browser(ledger)
