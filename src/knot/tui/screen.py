"""屏幕缓冲：只在变更行重绘，宽字符占位。"""

from __future__ import annotations

import sys

from knot.core.width import char_width
from knot.tui import term


class Screen:
    def __init__(self, rows: int | None = None, cols: int | None = None) -> None:
        detected_rows, detected_cols = term.size()
        self.rows = rows or detected_rows
        self.cols = cols or detected_cols
        self.buf: list[list[str]] = [[" "] * self.cols for _ in range(self.rows)]
        self.prev: list[str] | None = None

    def clear(self) -> None:
        self.buf = [[" "] * self.cols for _ in range(self.rows)]

    def put(self, row: int, col: int, text: str, max_width: int | None = None) -> None:
        if row < 0 or row >= self.rows:
            return
        limit = self.cols if max_width is None else min(self.cols, col + max_width)
        cursor = col
        for ch in text:
            width = char_width(ch)
            if cursor + width > limit:
                break
            self.buf[row][cursor] = ch
            for offset in range(1, width):
                self.buf[row][cursor + offset] = ""
            cursor += width

    def hline(self, row: int, char: str = "─") -> None:
        self.put(row, 0, char * self.cols)

    def flush(self, out=None) -> None:
        out = out or sys.stdout
        current = ["".join(line) for line in self.buf]
        if self.prev is None:
            out.write("\033[2J\033[?25l\033[H")
        for index, line in enumerate(current):
            if self.prev is None or self.prev[index] != line:
                out.write(f"\033[{index + 1};1H\033[K{line}")
        out.write("\033[?7l")
        out.flush()
        self.prev = current

    def restore(self, out=None) -> None:
        out = out or sys.stdout
        out.write("\033[?7h\033[?25h\n")
        out.flush()
