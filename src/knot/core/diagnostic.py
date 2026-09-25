from __future__ import annotations

from dataclasses import dataclass

from knot.core.width import str_width

LEVEL_NAMES = {"error": "错误", "warning": "警告", "hint": "提示"}

LEVEL_ORDER = {"error": 0, "warning": 1, "hint": 2}


@dataclass(slots=True)
class Diagnostic:
    level: str
    file: str
    line: int
    col: int
    message: str
    suggestion: str | None = None
    snippet: str | None = None
    caret: str | None = None


def render(d: Diagnostic) -> str:
    lines = [f"{d.file}:{d.line}:{d.col}  {LEVEL_NAMES.get(d.level, d.level)}：{d.message}"]
    if d.snippet is not None:
        prefix = f"  {d.line} | "
        lines.append(prefix + d.snippet)
        head = d.snippet[: max(0, d.col - 1)]
        width = str_width(d.caret) if d.caret else 1
        lines.append(" " * (str_width(prefix) + str_width(head)) + "^" * max(1, width))
    if d.suggestion:
        lines.append(f"  提示：{d.suggestion}")
    return "\n".join(lines)


def render_all(diags: list[Diagnostic]) -> str:
    ordered = sorted(diags, key=lambda d: (d.file, d.line, d.col, LEVEL_ORDER.get(d.level, 9)))
    return "\n".join(render(d) for d in ordered)


def count(diags: list[Diagnostic], level: str) -> int:
    return sum(1 for d in diags if d.level == level)
