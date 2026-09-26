"""TUI 主程序：固定三栏布局 + 键位（a/e//f/t/s/?/q），不实现通用布局引擎。"""

from __future__ import annotations

import sys
from pathlib import Path

from knot.core.amount import fmt_amount
from knot.core.loader import load_book
from knot.core.query import Filter, select
from knot.core.report import expense_by_category, monthly_flow
from knot.core.writer import Edit, apply_edits, detect_style, render_transaction
from knot.tui import input as keys
from knot.tui import term
from knot.tui.screen import Screen
from knot.tui.widgets import list as list_widget
from knot.tui.widgets import spark
from knot.tui.widgets import tree as tree_widget
from knot.tui.widgets.form import Form

COL1 = 26
COL2_MIN = 34
KEYS_HINT = " a记账 e编辑 /搜索 f筛选 t图表 s排序 ?帮助 q退出"


class App:
    def __init__(self, ledger: Path, key_source: keys.KeySource | None = None, out=None) -> None:
        self.ledger = Path(ledger)
        self.keys = key_source or keys.KeySource()
        self.out = out or sys.stdout
        rows, cols = term.size()
        self.screen = Screen(rows, cols)
        self.transactions = list_widget.ListView(height=max(4, rows - 8))
        self.tree = tree_widget.TreeView(height=max(4, rows - 8))
        self.form: Form | None = None
        self.mode = "浏览"
        self.status = "就绪"
        self.sort_key = "日期"
        self.filter_account: str | None = None
        self.query = ""
        self.help_visible = False
        self.running = True
        self.book = None
        self.diagnostics = []
        self._cache = None

    def reload(self) -> None:
        _result, book, diags = load_book(self.ledger, missing_ok=True)
        self.book = book
        self.diagnostics = [d for d in diags if d.level in ("error", "warning")]
        transactions = select(book.transactions, Filter(account=self.filter_account, limit=500))
        if self.sort_key == "金额":
            transactions = sorted(
                transactions,
                key=lambda tx: max(
                    (abs(p.units.number) for p in tx.postings if p.units), default=0
                ),
            )
        rows, raw = list_widget.build_rows(transactions)
        self.transactions.query = self.query
        self.transactions.set_rows(rows, raw)
        self.tree.build(book, self.filter_account)

    # ---------- 渲染 ----------

    def render(self) -> None:
        screen = self.screen
        rows, cols = screen.rows, screen.cols
        overview = ""
        if self.book is not None:
            overview = (
                f"交易 {len(self.book.transactions)} 笔 · "
                f"科目 {len(self.book.used_accounts())} 个 · 诊断 {len(self.diagnostics)} 条"
            )
        screen.put(0, 0, f" 结绳 Knot · {self.ledger.name}  {overview}", cols)
        screen.hline(1)
        col2 = max(COL2_MIN, cols - COL1 - 30)
        col3 = max(24, cols - COL1 - col2 - 4)
        screen.put(2, 1, "科目树", COL1 - 2)
        screen.put(2, COL1 + 2, f"流水（{self.transactions.status()}）", col2)
        screen.put(2, COL1 + col2 + 4, "详情", col3)
        screen.hline(3)

        for index, text in enumerate(self.tree.visible()):
            marker = ">" if index + self.tree.offset == self.tree.selected else " "
            screen.put(4 + index, 1, marker + text, COL1 - 2)
        for index, text in enumerate(self.transactions.visible()):
            marker = ">" if index + self.transactions.offset == self.transactions.selected else " "
            screen.put(4 + index, COL1 + 2, marker + text, col2)
        self._render_detail(4, COL1 + col2 + 4, col3)
        self._render_footer(rows - 1, cols)

    def _render_detail(self, row: int, col: int, width: int) -> None:
        screen = self.screen
        if self.form is not None:
            screen.put(row, col, "记一笔（Tab 切换 / Enter 输入 / Esc 取消 / s 保存）", width)
            for index, line in enumerate(self.form.render_lines(width)):
                screen.put(row + 1 + index, col, line, width)
            return
        transaction = self.transactions.current()
        if transaction is None:
            screen.put(row, col, "（没有可显示的流水）", width)
            return
        lines = [
            f"日期 {transaction.date.isoformat()}",
            f"标志 {transaction.flag.value}",
            f"收款方 {transaction.payee or '-'}",
            f"摘要 {transaction.narration or '-'}",
        ]
        for posting in transaction.postings[:4]:
            amount = fmt_amount(posting.units.number) if posting.units else "-"
            lines.append(f"{posting.account} {amount}{'（自动）' if posting.generated else ''}")
        if transaction.tags:
            lines.append("标签 " + " ".join(sorted(transaction.tags)))
        for index, line in enumerate(lines):
            screen.put(row + index, col, line, width)
        if self.book is not None:
            values = [item["支出"] for item in monthly_flow(self.book)[-12:]]
            if values:
                screen.put(
                    row + len(lines) + 1,
                    col,
                    "本月支出 " + spark.render(values, width=max(8, width - 12)),
                    width,
                )

    def _render_footer(self, row: int, cols: int) -> None:
        screen = self.screen
        screen.hline(max(0, row - 1))
        if self.help_visible:
            for index, line in enumerate(keys.HELP_TEXT):
                screen.put(row - 4 + index, 1, line, cols)
            return
        screen.put(row, 0, f"  [{self.mode}] {self.status}", max(10, cols - len(KEYS_HINT)))
        screen.put(row, max(0, cols - len(KEYS_HINT) - 1), KEYS_HINT)

    def draw(self) -> None:
        self.render()
        self.screen.flush(self.out)

    # ---------- 交互 ----------

    def handle(self, key: str) -> None:
        if self.form is not None:
            self._handle_form(key)
            return
        if key in ("q", "quit", "\x03"):
            self.running = False
        elif key in ("up", "k"):
            self.transactions.move(-1)
        elif key in ("down", "j"):
            self.transactions.move(1)
        elif key == "pgup":
            self.transactions.page(-1)
        elif key == "pgdn":
            self.transactions.page(1)
        elif key == "home":
            self.transactions.home()
        elif key == "end":
            self.transactions.end()
        elif key == "tab":
            self.tree.move(1)
        elif key == "enter":
            self.tree.toggle()
        elif key == "a":
            self.form, self.mode = Form(), "记账"
            self.status = "填写后用 s 保存，Esc 取消"
        elif key == "e":
            self._edit_narration()
        elif key == "/":
            self.query = (keys.fit_prompt("搜索", self.keys) or "").strip()
            self.transactions.filter(self.query)
            self.status = f"搜索：{self.query or '（清空）'}"
        elif key == "f":
            self.filter_account = keys.fit_prompt("筛选科目（空则清除）", self.keys) or None
            self.reload()
            self.status = f"筛选：{self.filter_account or '全部'}"
        elif key == "t":
            self._show_chart()
        elif key == "s":
            self.sort_key = "金额" if self.sort_key == "日期" else "日期"
            self.reload()
            self.status = f"排序：{self.sort_key}"
        elif key == "?":
            self.help_visible = not self.help_visible

    def _handle_form(self, key: str) -> None:
        assert self.form is not None
        if key == "esc":
            self.form, self.mode, self.status = None, "浏览", "已取消"
        elif key == "tab":
            self.form.move(1)
        elif key in ("up", "down"):
            self.form.move(-1 if key == "up" else 1)
        elif key == "s":
            missing = self.form.missing()
            if missing:
                self.status = "缺少必填：" + "、".join(missing)
            else:
                self._save_form()
        elif key == "enter":
            value = keys.fit_prompt(self.form.current(), self.keys)
            if value:
                self.form.set(value)

    def _save_form(self) -> None:
        from knot.core.actions import EntryRequest, write_entry

        assert self.form is not None
        payload = self.form.as_payload()
        try:
            entry = write_entry(
                EntryRequest(
                    amount=payload.get("金额", ""),
                    account=payload.get("科目", ""),
                    from_account=payload.get("来自"),
                    to_account=payload.get("去向"),
                    when=payload.get("日期"),
                    note=payload.get("摘要", ""),
                    payee=payload.get("收款方"),
                    tags=tuple(payload.get("标签") or ()),
                ),
                ledger=self.ledger,
                aliases=self._loaded.aliases,
                options=self.book.options,
                rules=self._loaded.rules,
                files=self._loaded.files,
            )
            self.status = f"已记入 {entry.target.name}"
        except Exception as exc:
            self.status = f"失败：{exc}"
            return
        self.form, self.mode, self._cache = None, "浏览", None
        self.reload()

    def _edit_narration(self) -> None:
        transaction = self.transactions.current()
        if transaction is None:
            self.status = "没有选中的交易"
            return
        value = keys.fit_prompt("新的摘要（空则取消）", self.keys)
        if not value:
            return
        transaction.narration = value
        path = Path(transaction.src_file)
        indent, newline = detect_style(path)
        apply_edits(
            path,
            [
                Edit(
                    transaction.src_line_start,
                    transaction.src_line_end,
                    render_transaction(transaction, indent, newline),
                )
            ],
        )
        self.status = f"已更新 {path.name}:{transaction.src_line_start}"
        self.reload()

    def _show_chart(self) -> None:
        if self.book is None:
            return
        rows = expense_by_category(self.book, top=8)
        if not rows:
            self.status = "暂无支出数据"
            return
        self.status = "支出排行：" + " ".join(
            f"{name.split(':')[-1]}({fmt_amount(value)})" for name, value in rows[:4]
        )

    @property
    def _loaded(self):
        if self._cache is None:
            loaded, _book, _diags = load_book(self.ledger, missing_ok=True)
            self._cache = loaded
        return self._cache

    def run(self) -> int:
        term.enable_vt()
        self.reload()
        self.draw()
        try:
            if term.is_tty():
                with term.RawMode():
                    while self.running:
                        self.handle(self.keys.next())
                        self.draw()
            else:
                while self.running:
                    self.handle(self.keys.next())
                    self.draw()
        except KeyboardInterrupt:
            self.running = False
        finally:
            self.screen.restore(self.out)
        return 0


def run_tui(ledger: Path, key_script: list[str] | None = None, out=None) -> int:
    return App(ledger, keys.KeySource(key_script), out).run()
