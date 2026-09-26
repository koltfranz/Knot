"""科目树：按 `:` 层级构建，支持折叠展开。"""

from __future__ import annotations

from dataclasses import dataclass, field

from knot.core.amount import fmt_amount, is_zero
from knot.core.book import Book


@dataclass
class TreeView:
    collapsed: set[str] = field(default_factory=set)
    selected: int = 0
    offset: int = 0
    height: int = 12
    lines: list[tuple[str, str]] = field(default_factory=list)  # (科目全名, 显示文本)
    book: Book | None = None
    account: str | None = None

    def build(self, book: Book, account: str | None = None) -> None:
        self.book, self.account = book, account
        names = [
            n
            for n in book.used_accounts()
            if account is None or n == account or n.startswith(account + ":")
        ]
        prefixes: set[str] = set()
        for name in names:
            parts = name.split(":")
            prefixes.update(":".join(parts[:i]) for i in range(1, len(parts) + 1))

        self.lines = []
        for node in sorted(prefixes):
            if any(
                node.startswith(parent + ":") and parent in self.collapsed for parent in prefixes
            ):
                continue
            depth = node.count(":")
            has_children = any(other.startswith(node + ":") for other in prefixes)
            marker = ("▾ " if node not in self.collapsed else "▸ ") if has_children else "  "
            totals = book.balance_of(node)
            text = "，".join(
                f"{fmt_amount(value)} {currency}"
                for currency, value in sorted(totals.items())
                if not is_zero(value)
            )
            label = node.split(":")[-1]
            self.lines.append((node, "  " * depth + marker + label + ("  " + text if text else "")))
        self.clamp()

    def clamp(self) -> None:
        if not self.lines:
            self.selected = self.offset = 0
            return
        self.selected = max(0, min(self.selected, len(self.lines) - 1))
        if self.selected < self.offset:
            self.offset = self.selected
        if self.selected >= self.offset + self.height:
            self.offset = self.selected - self.height + 1

    def move(self, delta: int) -> None:
        self.selected += delta
        self.clamp()

    def toggle(self) -> str | None:
        if not self.lines:
            return None
        name = self.lines[self.selected][0]
        if name in self.collapsed:
            self.collapsed.discard(name)
        else:
            self.collapsed.add(name)
        if self.book is not None:
            self.build(self.book, self.account)
            for index, (line_name, _text) in enumerate(self.lines):
                if line_name == name:
                    self.selected = index
                    break
            self.clamp()
        return name

    def current(self) -> str | None:
        return self.lines[self.selected][0] if self.lines else None

    def visible(self) -> list[str]:
        return [text for _name, text in self.lines[self.offset : self.offset + self.height]]
