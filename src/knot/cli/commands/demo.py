from __future__ import annotations

from importlib import resources
from pathlib import Path

from knot.cli.ansi import DIM, GREEN, YELLOW, style
from knot.core.normalize import KnotError

DEMO_NAME = "演示账本"


def add_parser(sub) -> None:
    p = sub.add_parser(
        "demo", aliases=["示例", "示例账本"], help="复制内置示例账本（覆盖全部功能）"
    )
    p.add_argument(
        "目录", nargs="?", default=DEMO_NAME, metavar="目录", help=f"目标目录，默认 {DEMO_NAME}"
    )
    p.add_argument("--覆盖", dest="overwrite", action="store_true", help="已存在的文件也覆盖")
    p.set_defaults(func=run)


def demo_root():
    return resources.files("knot").joinpath("data", DEMO_NAME)


def _walk(node, prefix: Path | None = None):
    prefix = Path() if prefix is None else prefix
    for child in node.iterdir():
        if child.name == "__pycache__":
            continue
        if child.is_dir():
            yield from _walk(child, prefix / child.name)
        else:
            yield prefix / child.name, child


def copy_demo(target: Path, *, overwrite: bool = False) -> tuple[list[Path], list[Path]]:
    root = demo_root()
    if not root.is_dir():
        raise KnotError("未找到内置示例账本（data/演示账本），安装包可能不完整")
    created: list[Path] = []
    skipped: list[Path] = []
    for relative, node in sorted(_walk(root), key=lambda item: str(item[0])):
        destination = target / relative
        if destination.exists() and not overwrite:
            skipped.append(destination)
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(node.read_bytes())
        created.append(destination)
    if not created and not skipped:
        raise KnotError("示例账本为空，安装包可能不完整")
    return created, skipped


def _quote(text: str) -> str:
    return f'"{text}"' if " " in text else text


def demo_commands(target: Path) -> list[str]:
    """复制完成后打印的演示清单：覆盖命令、报表与全部 7 种图表。"""
    ledger = f"--账本 {_quote(str(target / 'main.knot'))}"
    return [
        f"knot open {_quote(str(target))}                 # 终端界面：鼠标单击选择、Ctrl+单击多选",
        f"knot {ledger} 报 概况          # 概览",
        f"knot {ledger} 余 --树           # 科目余额（树）",
        f"knot {ledger} 预算              # 预算进度",
        f"knot {ledger} 持仓              # 投资持仓与盈亏",
        f"knot {ledger} 图 支出 -o 收支.svg         # 柱：月度收支",
        f"knot {ledger} 图 净资产 -o 净值.svg       # 线：净资产趋势",
        f"knot {ledger} 图 分类 -o 分类饼.svg       # 饼：支出分类占比",
        f"knot {ledger} 图 分类 --类型 树 -o 分类树.svg   # 树：分类面积",
        f"knot {ledger} 图 日历 -o 日历.svg         # 热力：消费日历",
        f"knot {ledger} 图 预算 -o 预算.svg         # 仪表：预算进度",
        f"knot {ledger} 图 现金流 -o 瀑布.svg       # 瀑布：现金流",
        f"knot {ledger} 服务 --打开浏览器   # 浏览器界面（同一账本）",
    ]


def run(args) -> int:
    target = Path(args.目录)
    created, skipped = copy_demo(target, overwrite=args.overwrite)
    for path in created:
        print(style(f"已生成：{path}", GREEN))
    for path in skipped:
        print(style(f"已存在，跳过：{path}（加 --覆盖 可重写）", YELLOW))
    print()
    print(style(f"示例账本已就绪：{target / 'main.knot'}", GREEN))
    print(style("试试这些命令：", DIM))
    for command in demo_commands(target):
        print(f"  {command}")
    return 0
