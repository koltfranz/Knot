"""TUI 主程序：固定三栏布局 + 键位与鼠标（选择、多选、批量操作）。"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from knot.core.amount import fmt_amount
from knot.core.bulk import (
    delete_transactions,
    export_transactions,
    format_totals,
    selectable,
    selection_key,
    summarize,
    tag_transactions,
)
from knot.core.loader import load_book
from knot.core.query import Filter, select
from knot.core.recur import is_generated
from knot.core.report import expense_by_category, monthly_flow
from knot.core.width import str_width
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
ROW_START = 4
KEYS_HINT = " a记账 e编辑 /搜索 f筛选 t图表 s排序 空格标记 b批量 ?帮助 q退出"
BATCH_MENU = (
    ("1", "汇总选中（笔数与收支合计）"),
    ("2", "批量打标签"),
    ("3", "导出选中（.csv / .json）"),
    ("4", "删除选中（写回前备份 .bak）"),
    ("5", "清空选择"),
)
CONFIRM_WORDS = ("y", "yes", "是", "确认")


@dataclass
class Layout:
    rows: int
    cols: int
    tree_x: int
    tree_w: int
    list_x: int
    list_w: int
    detail_x: int
    detail_w: int
    footer_row: int


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
        self.status = "就绪 · 鼠标：单击选择 / Ctrl+单击多选 / 滚轮滚动（空格标记、b 批量菜单）"
        self.sort_key = "日期"
        self.filter_account: str | None = None
        self.query = ""
        self.help_visible = False
        self.menu_visible = False
        self.marks: set[tuple[str, int]] = set()
        self.running = True
        self.book = None
        self.diagnostics = []
        self._cache = None

    def layout(self) -> Layout:
        rows, cols = self.screen.rows, self.screen.cols
        list_w = max(COL2_MIN, cols - COL1 - 30)
        detail_w = max(24, cols - COL1 - list_w - 4)
        return Layout(
            rows=rows,
            cols=cols,
            tree_x=1,
            tree_w=COL1 - 2,
            list_x=COL1 + 2,
            list_w=list_w,
            detail_x=COL1 + list_w + 4,
            detail_w=detail_w,
            footer_row=rows - 1,
        )

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

    def marked_transactions(self) -> list:
        if self.book is None:
            return []
        return [tx for tx in self.book.transactions if selection_key(tx) in self.marks]

    # ---------- 渲染 ----------

    def render(self) -> None:
        screen = self.screen
        layout = self.layout()
        overview = ""
        if self.book is not None:
            overview = (
                f"交易 {len(self.book.transactions)} 笔 · "
                f"科目 {len(self.book.used_accounts())} 个 · 诊断 {len(self.diagnostics)} 条"
            )
        screen.put(0, 0, f" 结绳 Knot · {self.ledger.name}  {overview}", layout.cols)
        screen.hline(1)
        screen.put(2, layout.tree_x, "科目树", layout.tree_w)
        screen.put(2, layout.list_x, f"流水（{self.transactions.status()}）", layout.list_w)
        screen.put(2, layout.detail_x, "详情", layout.detail_w)
        screen.hline(3)

        for index, text in enumerate(self.tree.visible()):
            marker = ">" if index + self.tree.offset == self.tree.selected else " "
            screen.put(ROW_START + index, layout.tree_x, marker + text, layout.tree_w)
        for index, text in enumerate(self.transactions.visible()):
            position = index + self.transactions.offset
            cursor = ">" if position == self.transactions.selected else " "
            source = self.transactions.raw
            item = source[position] if position < len(source) else None
            marked = item is not None and selection_key(item) in self.marks
            screen.put(ROW_START + index, layout.list_x, f"{cursor}{'✓' if marked else ' '}{text}")
        self._render_detail(ROW_START, layout.detail_x, layout.detail_w)
        self._render_footer(layout)

    def _render_detail(self, row: int, col: int, width: int) -> None:
        screen = self.screen
        if self.form is not None:
            screen.put(row, col, "记一笔（Tab 切换 / Enter 输入 / Esc 取消 / s 保存）", width)
            for index, line in enumerate(self.form.render_lines(width)):
                screen.put(row + 1 + index, col, line, width)
            return
        if self.menu_visible:
            screen.put(row, col, "批量操作（数字键或鼠标点击）", width)
            for index, (key, label) in enumerate(BATCH_MENU):
                screen.put(row + 1 + index, col, f" {key}  {label}", width)
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
        if is_generated(transaction):
            lines.append("来源 定期模板展开（请在模板行上改）")
        for posting in transaction.postings[:4]:
            amount = fmt_amount(posting.units.number) if posting.units else "-"
            lines.append(f"{posting.account} {amount}{'（自动）' if posting.generated else ''}")
        if transaction.tags:
            lines.append("标签 " + " ".join(sorted(transaction.tags)))
        if self.marks:
            summary = summarize(self.marked_transactions())
            lines.append(f"已选 {summary['笔数']} 笔 · {format_totals(summary['收支合计'])}")
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

    def _render_footer(self, layout: Layout) -> None:
        screen = self.screen
        row = layout.footer_row
        screen.hline(max(0, row - 1))
        if self.help_visible:
            start = max(0, row - len(keys.HELP_TEXT) - 1)
            for index, line in enumerate(keys.HELP_TEXT):
                screen.put(start + index, 1, line, layout.cols)
            return
        status = self.status
        if self.marks:
            status = f"{status} · 已选 {len(self.marks)} 笔（b 批量）"
        hint_x = max(0, layout.cols - str_width(KEYS_HINT) - 1)
        screen.put(row, 0, f"  [{self.mode}] {status}", max(10, hint_x - 2))
        screen.put(row, hint_x, KEYS_HINT)

    def draw(self) -> None:
        self.render()
        self.screen.flush(self.out)

    # ---------- 交互 ----------

    def handle(self, event: str) -> None:
        if self.form is not None:
            self._handle_form(event)
            return
        if keys.is_mouse(event):
            self._handle_mouse(event)
            return
        if self.menu_visible and self._handle_menu(event):
            return
        if event in ("q", "quit", "\x03"):
            self.running = False
        elif event in ("up", "k"):
            self.transactions.move(-1)
        elif event in ("down", "j"):
            self.transactions.move(1)
        elif event == "pgup":
            self.transactions.page(-1)
        elif event == "pgdn":
            self.transactions.page(1)
        elif event == "home":
            self.transactions.home()
        elif event == "end":
            self.transactions.end()
        elif event == "tab":
            self.tree.move(1)
        elif event == "enter":
            self.tree.toggle()
        elif event in (" ", "space"):
            self._toggle_mark()
        elif event == "b":
            self.menu_visible = not self.menu_visible
            self.status = "批量操作：按数字键选择" if self.menu_visible else "就绪"
        elif event == "esc":
            self._clear_marks()
        elif event == "a":
            self.form, self.mode = Form(), "记账"
            self.status = "填写后用 s 保存，Esc 取消"
        elif event == "e":
            self._edit_narration()
        elif event == "/":
            self.query = (keys.fit_prompt("搜索", self.keys) or "").strip()
            self.transactions.filter(self.query)
            self.status = f"搜索：{self.query or '（清空）'}"
        elif event == "f":
            self.filter_account = keys.fit_prompt("筛选科目（空则清除）", self.keys) or None
            self.reload()
            self.status = f"筛选：{self.filter_account or '全部'}"
        elif event == "t":
            self._show_chart()
        elif event == "s":
            self.sort_key = "金额" if self.sort_key == "日期" else "日期"
            self.reload()
            self.status = f"排序：{self.sort_key}"
        elif event == "?":
            self.help_visible = not self.help_visible

    def _handle_menu(self, event: str) -> bool:
        """批量菜单按键；返回是否已消费该事件。"""
        if event in ("esc", "b", "q"):
            self.menu_visible = False
            self.status = "就绪"
            return True
        actions = {
            "1": self._show_summary,
            "2": self._tag_selected,
            "3": self._export_selected,
            "4": self._delete_selected,
            "5": self._clear_marks,
        }
        action = actions.get(event)
        if action is None:
            return False
        self.menu_visible = False
        action()
        return True

    def _handle_mouse(self, event: str) -> None:
        parsed = keys.parse_mouse(event)
        if parsed is None:
            return
        name, x, y = parsed
        button, ctrl, _shift = keys.mouse_button(name)
        layout = self.layout()
        if button in ("wheel-up", "wheel-down"):
            step = -3 if button == "wheel-up" else 3
            if x - 1 >= layout.list_x:
                self.transactions.move(step)
            else:
                self.tree.move(step)
            return
        if y - 1 == layout.footer_row:
            if not button.startswith("left"):
                return
            for start, end, key in keys.footer_hits(KEYS_HINT, layout.cols):
                if start <= x - 1 <= end:
                    self.handle(key)
                    return
            return
        row = y - 1 - ROW_START
        if row < 0 or y - 1 >= layout.footer_row:
            return
        if button in ("left", "drag-left"):
            pass
        elif button != "drag-left":
            return
        if x - 1 < layout.list_x:
            self._click_tree(row)
        elif x - 1 < layout.detail_x:
            self._click_list(row, ctrl, drag=button == "drag-left")
        elif self.menu_visible:
            self._click_menu(row)

    def _click_tree(self, row: int) -> None:
        index = self.tree.offset + row
        if not 0 <= index < len(self.tree.lines):
            return
        if index == self.tree.selected:
            name = self.tree.toggle()
            self.status = f"科目：{name}" if name else self.status
            return
        self.tree.selected = index
        self.tree.clamp()
        self.status = f"科目：{self.tree.current() or '-'}"

    def _click_list(self, row: int, ctrl: bool, drag: bool = False) -> None:
        index = self.transactions.index_at(row)
        if index is None:
            return
        self.transactions.selected = index
        self.transactions.clamp()
        if ctrl:
            check = self.transactions.current()
            key = selection_key(check) if check is not None else None
            if drag:
                if key is not None and key not in self.marks:
                    self.marks.add(key)
                    self._refresh_mark_status()
            else:
                self._toggle_mark()
            return
        transaction = self.transactions.current()
        if transaction is not None:
            label = transaction.payee or transaction.narration or ""
            self.status = f"{transaction.date.isoformat()} {label}".strip()

    def _click_menu(self, row: int) -> None:
        index = row - 1
        if 0 <= index < len(BATCH_MENU):
            self._handle_menu(BATCH_MENU[index][0])

    def _toggle_mark(self) -> None:
        transaction = self.transactions.current()
        if transaction is None:
            self.status = "没有选中的交易"
            return
        key = selection_key(transaction)
        if key in self.marks:
            self.marks.discard(key)
        else:
            self.marks.add(key)
        self._refresh_mark_status()

    def _clear_marks(self) -> None:
        if not self.marks:
            return
        self.marks.clear()
        self.status = "已清空选择"

    def _refresh_mark_status(self) -> None:
        if not self.marks:
            self.status = "已清空选择"
            return
        summary = summarize(self.marked_transactions())
        self.status = f"已选 {summary['笔数']} 笔 · 收支合计 {format_totals(summary['收支合计'])}"

    def _show_summary(self) -> None:
        summary = summarize(self.marked_transactions())
        if not summary["笔数"]:
            self.status = "尚未选择交易：空格或 Ctrl+单击标记"
            return
        self.status = f"已选 {summary['笔数']} 笔 · 收支合计 {format_totals(summary['收支合计'])}"

    def _tag_selected(self) -> None:
        selected = self.marked_transactions()
        if not selected:
            self.status = "尚未选择交易"
            return
        value = keys.fit_prompt("标签（逗号分隔）", self.keys)
        if not value:
            return
        tags = [item.strip() for item in value.replace("，", ",").split(",") if item.strip()]
        try:
            result = tag_transactions(selected, tags)
        except Exception as exc:
            self.status = f"打标签失败：{exc}"
            return
        self.status = f"已给 {result.changed} 笔加上 {'、'.join(tags)}"
        self._after_write()

    def _export_selected(self) -> None:
        selected = self.marked_transactions()
        if not selected:
            self.status = "尚未选择交易"
            return
        default = f"导出-{date.today().strftime('%Y%m%d')}.csv"
        value = keys.fit_prompt(f"导出文件（默认 {default}）", self.keys) or default
        target = Path(value)
        fmt = "json" if target.suffix.lower() == ".json" else "csv"
        try:
            count, path = export_transactions(selected, target, fmt)
        except Exception as exc:
            self.status = f"导出失败：{exc}"
            return
        self.status = f"已导出 {count} 条分录 → {path}"

    def _delete_selected(self) -> None:
        selected = self.marked_transactions()
        if not selected:
            self.status = "尚未选择交易"
            return
        picked, skipped = selectable(selected)
        if not picked:
            self.status = "选中的都是定期模板展开的交易，不能删除"
            return
        hint = f"确认删除 {len(picked)} 笔"
        if skipped:
            hint += f"（跳过 {skipped} 笔定期展开）"
        answer = keys.fit_prompt(f"{hint}；输入 y 确认", self.keys)
        if (answer or "").strip().lower() not in CONFIRM_WORDS:
            self.status = "已取消删除"
            return
        try:
            result = delete_transactions(picked)
        except Exception as exc:
            self.status = f"删除失败：{exc}"
            return
        backups = "、".join(path.name for path in result.backups)
        self.status = f"已删除 {result.changed} 笔（备份：{backups or '无'}）"
        self._after_write()

    def _after_write(self) -> None:
        self.marks.clear()
        self.menu_visible = False
        self._cache = None
        self.reload()

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
        if is_generated(transaction):
            self.status = "定期模板展开的交易：请直接改模板行，或在模板上删改"
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

    def _sync_size(self) -> None:
        rows, cols = term.size()
        if (rows, cols) == (self.screen.rows, self.screen.cols):
            return
        self.screen = Screen(rows, cols)
        self.transactions.height = max(4, rows - 8)
        self.tree.height = max(4, rows - 8)
        self.transactions.clamp()
        self.tree.clamp()

    def _loop(self) -> None:
        while self.running:
            self._sync_size()
            event = self.keys.next()
            if event == "resize":
                self._sync_size()
                continue
            self.handle(event)
            self.draw()

    def run(self) -> int:
        term.enable_vt()
        self.reload()
        self.draw()
        try:
            if term.is_tty():
                with term.RawMode():
                    self._loop()
            else:
                self._loop()
        except KeyboardInterrupt:
            self.running = False
        finally:
            self.screen.restore(self.out)
        return 0


def run_tui(ledger: Path, key_script: list[str] | None = None, out=None) -> int:
    return App(ledger, keys.KeySource(key_script), out).run()
