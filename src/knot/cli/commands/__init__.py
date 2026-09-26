"""各子命令实现。"""

from __future__ import annotations

import sys

from knot.cli.ansi import RED, style
from knot.core.diagnostic import Diagnostic, render_all


def abort_on_errors(diags: list[Diagnostic]) -> bool:
    """存在错误级诊断时输出到 stderr 并指示调用方终止。"""
    errors = [d for d in diags if d.level == "error"]
    if not errors:
        return False
    print(render_all(errors), file=sys.stderr)
    print(style(f"错误 {len(errors)}，请先修复账本", RED), file=sys.stderr)
    return True
