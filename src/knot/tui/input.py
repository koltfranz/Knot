"""键位与输入辅助。"""

from __future__ import annotations

import sys

from knot.tui import term

HELP_TEXT = [
    "a  记一笔        /  搜索         t  图表          ?  帮助",
    "e  编辑摘要      f  按科目筛选    s  切换排序      q  退出",
    "↑↓ 移动          PgUp/PgDn 翻页  Enter 确认       Tab 切换字段",
]


class KeySource:
    """按键来源：交互模式读键盘；测试模式按脚本回放。"""

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


def flush_stdout() -> None:
    sys.stdout.flush()
