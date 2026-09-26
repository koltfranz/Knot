from __future__ import annotations

import io
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from knot.core.loader import load_book
from knot.tui.app import App
from knot.tui.screen import Screen
from knot.tui.widgets import spark
from knot.tui.widgets.form import Form
from knot.tui.widgets.list import ListView, build_rows
from knot.tui.widgets.tree import TreeView

LEDGER = """option "strict" "off"

2026-01-01 open 资产:现金 CNY
2026-01-01 open 权益:期初

2026-01-01 * "期初"
  资产:现金     1,000.00 CNY
  权益:期初

2026-01-20 * "外卖"  费用:餐饮:外卖  50.00 CNY  @ 资产:现金
2026-02-10 * "工资"  收入:工资  -8,000.00 CNY  @ 资产:现金
"""


class ScreenTest(unittest.TestCase):
    def test_wide_char_placeholder(self) -> None:
        screen = Screen(rows=3, cols=10)
        screen.put(0, 0, "资产A")
        row = screen.buf[0]
        self.assertEqual(row[0], "资")
        self.assertEqual(row[1], "")
        self.assertEqual(row[2], "产")
        self.assertEqual(row[3], "")
        self.assertEqual(row[4], "A")

    def test_flush_only_changed_lines(self) -> None:
        screen = Screen(rows=3, cols=10)
        screen.put(0, 0, "第一行")
        first = io.StringIO()
        screen.flush(first)
        self.assertIn("\033[2J", first.getvalue())

        screen.put(1, 0, "第二行")
        second = io.StringIO()
        screen.flush(second)
        self.assertIn("\033[2;1H", second.getvalue())
        self.assertNotIn("\033[1;1H", second.getvalue())

        third = io.StringIO()
        screen.flush(third)
        self.assertNotIn("\033[", third.getvalue().replace("\033[?7l", ""))

    def test_truncate_and_clip(self) -> None:
        screen = Screen(rows=1, cols=6)
        screen.put(0, 0, "一二三四五")
        self.assertEqual("".join(screen.buf[0]), "一二三")

    def test_restore_escapes(self) -> None:
        out = io.StringIO()
        Screen(rows=2, cols=4).restore(out)
        self.assertIn("\033[?25h", out.getvalue())


class SparkTest(unittest.TestCase):
    def test_empty(self) -> None:
        self.assertEqual(spark.render([]), "")

    def test_braille_range(self) -> None:
        text = spark.render([Decimal("0"), Decimal("10"), Decimal("5"), Decimal("20")])
        self.assertTrue(text)
        for char in text:
            self.assertGreaterEqual(ord(char), 0x2800)
            self.assertLessEqual(ord(char), 0x28FF)

    def test_width_bucketing(self) -> None:
        values = [Decimal(index) for index in range(100)]
        text = spark.render(values, width=10)
        self.assertLessEqual(len(text), 10)

    def test_flat_series(self) -> None:
        text = spark.render([Decimal("5")] * 4)
        self.assertEqual(len(set(text)), 1)


class ListViewTest(unittest.TestCase):
    def test_navigation_and_pages(self) -> None:
        view = ListView(height=3)
        view.set_rows([f"行{index}" for index in range(10)])
        self.assertEqual(view.visible(), ["行0", "行1", "行2"])
        view.move(4)
        self.assertEqual(view.selected, 4)
        self.assertEqual(view.visible()[0], "行2")
        view.page(1)
        self.assertEqual(view.selected, 7)
        view.end()
        self.assertEqual(view.status(), "10/10")
        view.home()
        self.assertEqual(view.selected, 0)

    def test_filter(self) -> None:
        rows, raw = build_rows_from_ledger()
        view = ListView(height=5)
        view.set_rows(rows, raw)
        view.filter("外卖")
        self.assertEqual(len(view.rows), 1)
        self.assertIn("外卖", view.rows[0])
        view.filter("")
        self.assertGreater(len(view.rows), 1)

    def test_keeps_selection_by_key(self) -> None:
        rows, raw = build_rows_from_ledger()
        view = ListView(height=5)
        view.set_rows(rows, raw)
        view.move(1)
        key = view.current_key()
        view.set_rows(rows, raw)
        self.assertEqual(view.current_key(), key)


def build_rows_from_ledger():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "main.knot"
        path.write_text(LEDGER, encoding="utf-8")
        _result, book, _diags = load_book(path)
        return build_rows(book.transactions)


class TreeViewTest(unittest.TestCase):
    def _build(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "main.knot"
            path.write_text(LEDGER, encoding="utf-8")
            _result, book, _diags = load_book(path)
            view = TreeView(height=10)
            view.build(book)
            return view

    def test_tree_lines(self) -> None:
        view = self._build()
        names = [name for name, _text in view.lines]
        self.assertIn("资产", names)
        self.assertIn("资产:现金", names)
        self.assertIn("费用:餐饮:外卖", names)
        self.assertTrue(any(text.startswith("  ▾") for _name, text in view.lines[1:]))

    def test_collapse_hides_children(self) -> None:
        view = self._build()
        for index, (name, _text) in enumerate(view.lines):
            if name == "资产":
                view.selected = index
                break
        view.toggle()
        names = [name for name, _text in view.lines]
        self.assertNotIn("资产:现金", names)
        self.assertIn("资产", names)

    def test_filter_account(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "main.knot"
            path.write_text(LEDGER, encoding="utf-8")
            _result, book, _diags = load_book(path)
            view = TreeView(height=10)
            view.build(book, account="费用")
            names = [name for name, _text in view.lines]
            self.assertTrue(all(name.startswith("费用") for name in names))


class FormTest(unittest.TestCase):
    def test_navigation_and_validation(self) -> None:
        form = Form()
        self.assertEqual(form.current(), "金额")
        self.assertEqual(len(form.missing()), 2)
        form.set("38")
        form.move(1)
        self.assertEqual(form.current(), "科目")
        form.set("餐饮")
        self.assertEqual(form.missing(), [])
        payload = form.as_payload()
        self.assertEqual(payload["金额"], "38")
        self.assertEqual(payload["科目"], "餐饮")

    def test_tags_split(self) -> None:
        form = Form(values={"标签": "工作，报销, 出差"})
        self.assertEqual(form.as_payload()["标签"], ["工作", "报销", "出差"])

    def test_render_lines_marks_current(self) -> None:
        form = Form()
        lines = form.render_lines(40)
        self.assertTrue(lines[0].startswith("▸"))
        self.assertTrue(any("必填" in line for line in lines))


class AppTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.ledger = Path(self._tmp.name) / "main.knot"
        self.ledger.write_text(LEDGER, encoding="utf-8")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _run(self, script: list[str]) -> tuple[int, str, App]:
        out = io.StringIO()
        app = App(
            self.ledger, __import__("knot.tui.input", fromlist=["KeySource"]).KeySource(script), out
        )
        code = app.run()
        return code, out.getvalue(), app

    def test_navigation_and_help(self) -> None:
        code, output, app = self._run(["down", "?", "?", "q"])
        self.assertEqual(code, 0)
        self.assertIn("结绳 Knot", output)
        self.assertIn("科目树", output)
        self.assertFalse(app.help_visible)

    def test_search_and_sort(self) -> None:
        code, _output, app = self._run(["/", "外卖", "s", "q"])
        self.assertEqual(code, 0)
        self.assertIn(app.sort_key, ("日期", "金额"))
        self.assertEqual(len(app.transactions.rows), 1)

    def test_record_transaction_through_form(self) -> None:
        script = ["a", "enter", "38", "tab", "enter", "餐饮", "tab", "enter", "现金", "s", "q"]
        code, _output, app = self._run(script)
        self.assertEqual(code, 0)
        text = self.ledger.read_text(encoding="utf-8")
        self.assertIn("费用:餐饮", text)
        self.assertIn("38.00", text)
        self.assertIn("已记入", app.status)

    def test_edit_narration(self) -> None:
        code, _output, _app = self._run(["e", "改过的摘要", "q"])
        self.assertEqual(code, 0)
        self.assertIn("改过的摘要", self.ledger.read_text(encoding="utf-8"))

    def test_chart_status(self) -> None:
        _code, _output, app = self._run(["t", "q"])
        self.assertIn("支出排行", app.status)

    def test_detail_panel_renders_selected(self) -> None:
        _code, output, _app = self._run(["down", "q"])
        self.assertIn("日期 2026-", output)

    def test_empty_ledger(self) -> None:
        empty = Path(self._tmp.name) / "空.knot"
        out = io.StringIO()
        from knot.tui.input import KeySource

        app = App(empty, KeySource(["q"]), out)
        self.assertEqual(app.run(), 0)
        self.assertIn("交易 0 笔", out.getvalue())

    def test_line_budget(self) -> None:
        """TUI 模块总行数 SHOULD ≤ 800（开发文档 9.4）。"""
        root = Path(__file__).resolve().parents[1] / "src" / "knot" / "tui"
        total = 0
        for path in root.rglob("*.py"):
            total += len(path.read_text(encoding="utf-8").splitlines())
        self.assertLessEqual(total, 800, f"TUI 代码 {total} 行，超出预算")


if __name__ == "__main__":
    unittest.main()
