"""键位与输入辅助。"""

from __future__ import annotations

import re
import sys

from knot.core.width import str_width
from knot.tui import term

HELP_TEXT = [
    "a 记一笔   e 编辑摘要   / 搜索   f 按科目筛选   t 图表排行   s 排序   ? 帮助   q 退出",
    "↑ ↓ 移动   PgUp/PgDn 翻页   Home/End 首尾   Enter 展开科目   Tab 切换表单字段",
    "空格 标记当前笔   Ctrl+单击 标记   b 批量操作（汇总/标签/导出/删除）   Esc 清空选择",
    "鼠标：单击选择流水或科目·滚轮滚动·点击底栏提示条等同按键（终端需支持鼠标上报）",
]


class KeySource:
    """按键来源：交互模式读键盘；测试模式按脚本回放（字符串脚本可含鼠标事件）。"""

    def __init__(self, script: list[str] | None = None) -> None:
        self._script = list(script or [])

    def next(self) -> str:
        if self._script:
            return self._script.pop(0)
        return term.read_key()

    def prompt(self, label: str) -> str:
        """需要输入中文/文本时切换到 cooked 模式。"""
        if self._script:
            return self._script.pop(0)
        return term.cooked_line(f"{label}：")


def fit_prompt(label: str, key_source: KeySource) -> str | None:
    value = key_source.prompt(label)
    return value.strip() or None


def is_mouse(event: str) -> bool:
    return event.startswith("mouse:")


def parse_mouse(event: str) -> tuple[str, int, int] | None:
    """mouse:ctrl-left:34:7 → ("ctrl-left", 34, 7)；解析失败返回 None。"""
    parts = event.split(":")
    if len(parts) != 4 or parts[0] != "mouse":
        return None
    try:
        return parts[1], int(parts[2]), int(parts[3])
    except ValueError:
        return None


def mouse_button(name: str) -> tuple[str, bool, bool]:
    """'ctrl-shift-left' → ('left', ctrl=True, shift=True)。"""
    ctrl = "ctrl" in name
    shift = "shift" in name
    button = name.replace("ctrl-", "").replace("shift-", "")
    return button, ctrl, shift


FOOTER_KEYS = {"空": " ", "spc": " "}


def footer_hits(hint: str, cols: int) -> list[tuple[int, int, str]]:
    """底栏提示条的可点击区间（按显示宽度计算）：[(起始列, 结束列, 等价键)]。"""
    offset = max(0, cols - str_width(hint) - 1)
    hits: list[tuple[int, int, str]] = []
    for match in re.finditer(r"\S+", hint):
        token = match.group(0)
        start = offset + str_width(hint[: match.start()])
        hits.append((start, start + str_width(token) - 1, FOOTER_KEYS.get(token[0], token[0])))
    return hits


def flush_stdout() -> None:
    sys.stdout.flush()
