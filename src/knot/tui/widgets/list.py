"""可滚动流水列表：方向键、PageUp/PageDown、搜索。"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ListView:
    rows: list[str] = field(default_factory=list)
    raw: list = field(default_factory=list)
    all_rows: list[str] = field(default_factory=list)
    all_raw: list = field(default_factory=list)
    selected: int = 0
    offset: int = 0
    height: int = 10
    query: str = ""

    def set_rows(self, rows: list[str], raw: list | None = None, keep: bool = True) -> None:
        self.all_rows = list(rows)
        self.all_raw = list(raw if raw is not None else rows)
        self.apply_filter(keep=keep)

    def apply_filter(self, keep: bool = True) -> None:
        previous = self.current_key() if keep else None
        if self.query:
            pairs = [
                (t, i) for t, i in zip(self.all_rows, self.all_raw, strict=False) if self.query in t
            ]
            self.rows = [t for t, _i in pairs]
            self.raw = [i for _t, i in pairs]
        else:
            self.rows, self.raw = list(self.all_rows), list(self.all_raw)
        self.selected = 0
        if previous is not None:
            for index, item in enumerate(self.raw):
                if self.key_of(item) == previous:
                    self.selected = index
                    break
        self.clamp()

    def key_of(self, item) -> str:
        return str(getattr(item, "src_line_start", "") or item)

    def current_key(self) -> str | None:
        if not self.raw or not (0 <= self.selected < len(self.raw)):
            return None
        return self.key_of(self.raw[self.selected])

    def current(self):
        return self.raw[self.selected] if self.raw else None

    def clamp(self) -> None:
        if not self.rows:
            self.selected = self.offset = 0
            return
        self.selected = max(0, min(self.selected, len(self.rows) - 1))
        if self.selected < self.offset:
            self.offset = self.selected
        if self.selected >= self.offset + self.height:
            self.offset = self.selected - self.height + 1

    def move(self, delta: int) -> None:
        self.selected += delta
        self.clamp()

    def page(self, direction: int) -> None:
        self.move(direction * max(1, self.height))

    def home(self) -> None:
        self.selected = 0
        self.clamp()

    def end(self) -> None:
        self.selected = len(self.rows) - 1
        self.clamp()

    def filter(self, query: str) -> None:
        self.query = query
        self.apply_filter(keep=False)

    def visible(self) -> list[str]:
        return self.rows[self.offset : self.offset + self.height]

    def status(self) -> str:
        return f"{self.selected + 1}/{len(self.rows)}" if self.rows else "无记录"


def build_rows(transactions: list) -> tuple[list[str], list]:
    """把交易渲染为列表文本与原始对象（日期 标志 摘要 科目 金额）。"""
    from knot.core.amount import fmt_amount

    rows = []
    for tx in transactions:
        posting = next((p for p in tx.postings if p.units and p.units.number > 0), None)
        posting = posting or next((p for p in tx.postings if p.units), None)
        amount = fmt_amount(posting.units.number) if posting and posting.units else ""
        account = posting.account if posting else ""
        label = tx.payee or tx.narration or ""
        rows.append(
            f"{tx.date.strftime('%m-%d')} {tx.flag.value} "
            f"{label[:12]:<12} {account[:18]:<18} {amount:>12}"
        )
    return rows, list(transactions)
