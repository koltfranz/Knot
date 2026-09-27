from __future__ import annotations

import io
import struct
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from knot.core.loader import load_book
from knot.tui import input as keys
from knot.tui import term
from knot.tui.app import KEYS_HINT, App
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

RECUR_LEDGER = """option "strict" "off"

2026-01-01 open 资产:现金 CNY
2026-01-01 open 权益:期初

2026-01-01 * "期初"
  资产:现金     1,000.00 CNY
  权益:期初

2026-01-01 recur "monthly" "房租" from 2026-01-01 to 2026-03-01
  费用:居住:房租   3,000.00 CNY  @ 资产:现金
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


class TermTest(unittest.TestCase):
    def test_parse_escape_keys(self) -> None:
        self.assertEqual(term.parse_escape(b"\x1b[A"), "up")
        self.assertEqual(term.parse_escape(b"\x1b[5~"), "pgup")
        self.assertEqual(term.parse_escape(b"\x1b[3~"), "delete")
        self.assertEqual(term.parse_escape(b"\x1b"), "esc")
        self.assertEqual(term.parse_escape(b"\x1bx"), "esc")

    def test_parse_escape_mouse(self) -> None:
        self.assertEqual(term.parse_escape(b"\x1b[<0;12;5M"), "mouse:left:12:5")
        self.assertEqual(term.parse_escape(b"\x1b[<16;3;4M"), "mouse:ctrl-left:3:4")
        self.assertEqual(term.parse_escape(b"\x1b[<64;9;9M"), "mouse:wheel-up:9:9")
        self.assertEqual(term.parse_escape(b"\x1b[<65;9;9M"), "mouse:wheel-down:9:9")
        self.assertEqual(term.parse_escape(b"\x1b[<32;7;2M"), "mouse:drag-left:7:2")
        self.assertEqual(term.parse_escape(b"\x1b[<0;12;5m"), "")

    def test_console_record_key(self) -> None:
        def key_event(down: int, vk: int, char: int) -> bytes:
            return struct.pack("<HxxiHHHHI", 0x0001, down, 1, vk, 0, char, 0)

        self.assertEqual(term.parse_console_record(key_event(1, 0x51, ord("q"))), "q")
        self.assertEqual(term.parse_console_record(key_event(0, 0x51, ord("q"))), "")
        self.assertEqual(term.parse_console_record(key_event(1, 0x26, 0)), "up")
        self.assertEqual(term.parse_console_record(key_event(1, 0x0D, 13)), "enter")

    def test_console_record_mouse(self) -> None:
        def mouse_event(x: int, y: int, buttons: int, control: int, flags: int) -> bytes:
            return struct.pack("<HxxhhIII", 0x0002, x, y, buttons, control, flags)

        self.assertEqual(term.parse_console_record(mouse_event(11, 4, 1, 0, 0)), "mouse:left:12:5")
        self.assertEqual(
            term.parse_console_record(mouse_event(11, 4, 1, 0, 0), (0, 1)), "mouse:left:12:4"
        )
        self.assertEqual(
            term.parse_console_record(mouse_event(11, 4, 1, 0x0008, 0)), "mouse:ctrl-left:12:5"
        )
        self.assertEqual(
            term.parse_console_record(mouse_event(11, 4, 120 << 16, 0, 0x0004)),
            "mouse:wheel-up:12:5",
        )
        self.assertEqual(
            term.parse_console_record(mouse_event(11, 4, (-120 & 0xFFFF) << 16, 0, 0x0004)),
            "mouse:wheel-down:12:5",
        )
        self.assertEqual(term.parse_console_record(mouse_event(11, 4, 0, 0, 0)), "")

    def test_console_record_resize(self) -> None:
        self.assertEqual(term.parse_console_record(b"\x04\x00"), "resize")


class InputTest(unittest.TestCase):
    def test_parse_mouse(self) -> None:
        self.assertEqual(keys.parse_mouse("mouse:ctrl-left:34:7"), ("ctrl-left", 34, 7))
        self.assertIsNone(keys.parse_mouse("up"))
        self.assertIsNone(keys.parse_mouse("mouse:left:x:1"))
        self.assertTrue(keys.is_mouse("mouse:left:1:1"))
        self.assertFalse(keys.is_mouse("left"))

    def test_mouse_button(self) -> None:
        self.assertEqual(keys.mouse_button("ctrl-left"), ("left", True, False))
        self.assertEqual(keys.mouse_button("shift-wheel-up"), ("wheel-up", False, True))

    def test_footer_hits(self) -> None:
        hits = keys.footer_hits(" a记账 q退出", 40)
        self.assertEqual([item[2] for item in hits], ["a", "q"])
        self.assertEqual(hits[0][0], 28)
        self.assertEqual(hits[1][0], 34)

        space = keys.footer_hits(" 空格标记", 40)
        self.assertEqual(space[0][2], " ")


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

    def test_index_at(self) -> None:
        view = ListView(height=2)
        view.set_rows([f"行{index}" for index in range(4)])
        self.assertEqual(view.index_at(0), 0)
        view.move(2)
        self.assertEqual(view.index_at(0), 1)
        self.assertEqual(view.index_at(1), 2)
        self.assertIsNone(view.index_at(2))
        self.assertIsNone(view.index_at(-1))


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
        app = App(self.ledger, keys.KeySource(script), out)
        code = app.run()
        return code, out.getvalue(), app

    def _app(self) -> App:
        return App(self.ledger, keys.KeySource([]), io.StringIO())

    def _scripted(self, app: App, script: list[str]) -> None:
        app.keys = keys.KeySource([*script, "q"])

    def _click(self, app: App, row: int, button: str = "left") -> str:
        return f"mouse:{button}:{app.layout().list_x + 1}:{4 + row + 1}"

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
        app = App(empty, keys.KeySource(["q"]), out)
        self.assertEqual(app.run(), 0)
        self.assertIn("交易 0 笔", out.getvalue())

    def test_mouse_click_selects_row(self) -> None:
        app = self._app()
        second, first = self._click(app, 1), self._click(app, 0)
        self._scripted(app, [second, first])
        self.assertEqual(app.run(), 0)
        self.assertEqual(app.transactions.selected, 0)

    def test_ctrl_click_marks_and_wheel_scrolls(self) -> None:
        app = self._app()
        first = self._click(app, 0, "ctrl-left")
        sweep = [self._click(app, 1, "ctrl-drag-left"), self._click(app, 2, "ctrl-drag-left")]
        wheel = f"mouse:wheel-down:{app.layout().list_x + 1}:6"
        self._scripted(app, [first, *sweep, wheel])
        self.assertEqual(app.run(), 0)
        self.assertEqual(len(app.marks), 3)
        self.assertEqual(app.transactions.selected, len(app.transactions.rows) - 1)

    def test_wheel_over_tree_moves_tree(self) -> None:
        app = self._app()
        self._scripted(app, ["mouse:wheel-down:3:6"])
        self.assertEqual(app.run(), 0)
        self.assertGreater(app.tree.selected, 0)

    def test_footer_click_triggers_key(self) -> None:
        app = self._app()
        start, _end, _key = next(
            item for item in keys.footer_hits(KEYS_HINT, app.screen.cols) if item[2] == "t"
        )
        self._scripted(app, [f"mouse:left:{start + 1}:{app.screen.rows}"])
        self.assertEqual(app.run(), 0)
        self.assertIn("支出排行", app.status)

    def test_space_and_esc_toggle_marks(self) -> None:
        code, _output, app = self._run(["down", " ", "esc", " ", "q"])
        self.assertEqual(code, 0)
        self.assertEqual(len(app.marks), 1)

    def test_batch_tag_selected(self) -> None:
        app = self._app()
        mark = self._click(app, 1, "ctrl-left")
        self._scripted(app, [mark, "b", "2", "报销,工作"])
        self.assertEqual(app.run(), 0)
        text = self.ledger.read_text(encoding="utf-8")
        self.assertIn("#报销", text)
        self.assertIn("#工作", text)
        self.assertIn("已给 1 笔加上", app.status)
        self.assertEqual(app.marks, set())

    def test_batch_delete_creates_backup(self) -> None:
        app = self._app()
        mark = self._click(app, 1, "ctrl-left")
        self._scripted(app, [mark, "b", "4", "y"])
        self.assertEqual(app.run(), 0)
        self.assertNotIn("外卖", self.ledger.read_text(encoding="utf-8"))
        backups = list(Path(self._tmp.name).glob("*.bak"))
        self.assertEqual(len(backups), 1)
        self.assertIn("外卖", backups[0].read_text(encoding="utf-8"))

    def test_batch_export_writes_csv(self) -> None:
        target = Path(self._tmp.name) / "导出.csv"
        app = self._app()
        mark = self._click(app, 1, "ctrl-left")
        self._scripted(app, [mark, "b", "3", str(target)])
        self.assertEqual(app.run(), 0)
        self.assertTrue(target.exists())
        self.assertIn("已导出", app.status)

    def test_batch_summary_status(self) -> None:
        app = self._app()
        mark = self._click(app, 1, "ctrl-left")
        self._scripted(app, [mark, "b", "1"])
        self.assertEqual(app.run(), 0)
        self.assertIn("收支合计", app.status)
        self.assertIn("50.00", app.status)

    def test_delete_cancelled_without_confirm(self) -> None:
        app = self._app()
        mark = self._click(app, 1, "ctrl-left")
        self._scripted(app, [mark, "b", "4", "n"])
        self.assertEqual(app.run(), 0)
        self.assertIn("外卖", self.ledger.read_text(encoding="utf-8"))
        self.assertEqual(app.status, "已取消删除")

    def test_generated_rows_are_marked(self) -> None:
        path = Path(self._tmp.name) / "定期.knot"
        path.write_text(RECUR_LEDGER, encoding="utf-8")
        out = io.StringIO()
        app = App(path, keys.KeySource(["q"]), out)
        self.assertEqual(app.run(), 0)
        self.assertTrue(any("⟳" in row for row in app.transactions.rows))

    def test_line_budget(self) -> None:
        """TUI 模块总行数 SHOULD ≤ 1500（开发文档 9.4；0.8.0 起含鼠标与批量操作）。"""
        root = Path(__file__).resolve().parents[1] / "src" / "knot" / "tui"
        total = 0
        for path in root.rglob("*.py"):
            total += len(path.read_text(encoding="utf-8").splitlines())
        self.assertLessEqual(total, 1500, f"TUI 代码 {total} 行，超出预算")


if __name__ == "__main__":
    unittest.main()
