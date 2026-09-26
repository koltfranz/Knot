from __future__ import annotations

import json
import sys
from pathlib import Path

from knot.cli.ansi import GREEN, YELLOW, style
from knot.core.convert import (
    DIRECTION_AUTO,
    DIRECTION_TO_FULL,
    DIRECTION_TO_HALF,
    SCOPE_ALL,
    SCOPE_SYNTAX,
    convert_file,
)
from knot.core.diagnostic import render_all
from knot.core.loader import Loader
from knot.core.normalize import KnotError

DIRECTIONS = {
    "自动": DIRECTION_AUTO,
    "全→半": DIRECTION_TO_HALF,
    "半→全": DIRECTION_TO_FULL,
    "auto": DIRECTION_AUTO,
    "to_half": DIRECTION_TO_HALF,
    "to_full": DIRECTION_TO_FULL,
}

SCOPES = {"句法": SCOPE_SYNTAX, "全部": SCOPE_ALL, "syntax": SCOPE_SYNTAX, "all": SCOPE_ALL}


def add_parser(sub) -> None:
    p = sub.add_parser("normalize", aliases=["规范", "nrm"], help="全角 / 半角一键规范化")
    p.add_argument("文件", nargs="*", metavar="文件", help="默认处理账本已加载的全部 .knot 文件")
    p.add_argument(
        "--方向", "--direction", dest="direction", choices=sorted(DIRECTIONS), default="自动"
    )
    p.add_argument("--范围", "--scope", dest="scope", choices=sorted(SCOPES), default="句法")
    p.add_argument(
        "--试运行", "--dry-run", dest="dry_run", action="store_true", help="只报告不写入"
    )
    p.add_argument(
        "--检查",
        "--check",
        dest="check_only",
        action="store_true",
        help="只检查是否需要规范化，需要则退出码 1",
    )
    p.add_argument(
        "--修复未闭合",
        dest="fix_unclosed",
        action="store_true",
        help="自动补全未闭合的引号与花括号",
    )
    p.add_argument("--json", dest="as_json", action="store_true", help="输出结构化 JSON")
    p.set_defaults(func=run)


def _targets(args) -> list[Path]:
    if args.文件:
        return [Path(item) for item in args.文件]
    result = Loader().load(Path(args.ledger))
    files = [f for f in result.files if f.suffix == ".knot"]
    if not files:
        raise KnotError(f"未找到可规范化的文件：{args.ledger}")
    return files


def run(args) -> int:
    direction = DIRECTIONS[args.direction]
    scope = SCOPES[args.scope]
    if direction == DIRECTION_TO_FULL and scope == SCOPE_SYNTAX:
        raise KnotError("半→全 只作用于文本范围，请加 --范围 全部")

    write = not (args.dry_run or args.check_only)
    payload: dict[str, dict] = {}
    reports = []
    diagnostics = []

    for path in _targets(args):
        if not path.exists():
            raise KnotError(f"文件不存在：{path}")
        report = convert_file(
            path,
            direction=direction,
            scope=scope,
            fix_unclosed=args.fix_unclosed,
            write=write,
        )
        reports.append((path, report))
        diagnostics.extend(report.diagnostics)
        payload[str(path)] = {
            "改动数": report.change_count,
            "改动明细": dict(sorted(report.changes.items())),
            "未闭合行": report.unclosed_lines,
            "不配对行": report.unbalanced_lines,
        }

    if args.as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        if diagnostics:
            print(render_all(diagnostics), file=sys.stderr)
        for path, report in reports:
            if not report.changed:
                print(style(f"无需规范化：{path}", GREEN))
                continue
            detail = "，".join(f"{k}×{v}" for k, v in sorted(report.changes.items()))
            head = "需要规范化" if not write else "已规范化"
            tag = YELLOW if not write else GREEN
            print(style(f"{head}：{path}", tag) + (f"（{detail}）" if detail else ""))

    if args.check_only:
        return 1 if any(report.changed for _path, report in reports) else 0
    return 0
