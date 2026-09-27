from __future__ import annotations

import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from knot.cli.main import main
from knot.core.actions import reclassify
from knot.core.aliases import AliasTable
from knot.core.loader import load_book
from knot.core.reconcile import mark_cleared, reconcile
from knot.tui.app import App
from knot.tui.input import KeySource

LEDGER = """option "strict" "off"

2026-01-01 open 资产:银行:招行 CNY

2026-01-01 * "期初"
  资产:银行:招行     10,000.00 CNY
  权益:期初

2026-01-01 recur "monthly" "房租" from 2026-01-01 to 2026-03-01
  费用:居住:房租   3,000.00 CNY  @ 资产:银行:招行

2026-02-05 "外卖"  费用:待分类  50.00 CNY  @ 资产:银行:招行
"""


class RecurSafetyTest(unittest.TestCase):
    """回归：对账标记与归类 MUST NOT 改写定期模板（多笔展开共享同一源行区间）。"""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name) / "main.knot"
        self.path.write_text(LEDGER, encoding="utf-8")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _text(self) -> str:
        return self.path.read_text(encoding="utf-8")

    def test_mark_cleared_keeps_recur_template(self) -> None:
        book = load_book(self.path)[1]
        report = reconcile(book, "资产:银行:招行")
        # 定期展开的交易不参与对账标记（模板在文件里已确定）
        self.assertGreater(report.generated, 0)
        self.assertTrue(all("房租" not in (tx.narration or "") for tx in report.pending))

        mark_cleared(report.pending)
        text = self._text()
        self.assertIn("recur", text, "定期模板 MUST 保留")
        self.assertIn('recur "monthly" "房租"', text)

        _result, _book, diags = load_book(self.path)
        self.assertEqual([d for d in diags if d.level == "error"], [])

        again = reconcile(load_book(self.path)[1], "资产:银行:招行")
        self.assertTrue(all("房租" not in (tx.narration or "") for tx in again.pending))
        self.assertEqual(len(again.pending), 0)

    def test_mark_cleared_marks_plain_transactions(self) -> None:
        book = load_book(self.path)[1]
        plain = [tx for tx in book.transactions if tx.narration == "外卖"]
        count = mark_cleared(plain)
        self.assertEqual(count, 1)
        self.assertIn(" P ", self._text())
        self.assertIn("recur", self._text())

    def test_reclassify_skips_recur_and_dedupes(self) -> None:
        changed, _files = reclassify(
            self.path, aliases=AliasTable(), payee="外卖", account="费用:餐饮:外卖"
        )
        self.assertEqual(changed, 1)
        text = self._text()
        self.assertIn("费用:餐饮:外卖", text)
        self.assertIn("recur", text)

    def test_duplicate_blocks_are_edited_once(self) -> None:
        book = load_book(self.path)[1]
        same = [tx for tx in book.transactions if tx.narration == "外卖"]
        duplicated = same + list(same)  # 模拟同一块被重复提交
        self.assertEqual(mark_cleared(duplicated), 1)
        _result, _book, diags = load_book(self.path)
        self.assertEqual([d for d in diags if d.level == "error"], [])


class TuiRecurEditTest(unittest.TestCase):
    """回归：TUI 编辑摘要 MUST NOT 改写定期模板（展开实例共享模板行区间）。"""

    def test_edit_narration_on_generated_transaction_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "main.knot"
            path.write_text(LEDGER, encoding="utf-8")
            before = path.read_text(encoding="utf-8")

            out = io.StringIO()
            app = App(path, KeySource(["down", "e", "改坏的摘要", "q"]), out)
            self.assertEqual(app.run(), 0)

            self.assertEqual(path.read_text(encoding="utf-8"), before, "定期模板 MUST 保持不变")
            self.assertIn("定期", app.status)


class RecurCommandTest(unittest.TestCase):
    """回归：定期模板展开后仍可被 `定期` 命令列出（曾经永远显示"没有模板"）。"""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name) / "main.knot"
        self.path.write_text(LEDGER, encoding="utf-8")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_templates_are_kept_on_book(self) -> None:
        from knot.cli.commands.recur import templates

        book = load_book(self.path)[1]
        self.assertEqual(len(templates(book)), 1)
        self.assertEqual(templates(book)[0].description, "房租")

    def test_recur_command_lists_templates(self) -> None:
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = main(["--账本", str(self.path), "定期"])
        output = buffer.getvalue()
        self.assertEqual(code, 0)
        self.assertIn("房租", output)
        self.assertNotIn("还没有定期交易模板", output)

    def test_recur_month_preview(self) -> None:
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = main(["--账本", str(self.path), "定期", "--月", "2026-02"])
        output = buffer.getvalue()
        self.assertEqual(code, 0)
        self.assertIn("2026-02-01", output)
        self.assertIn("3,000.00", output)


class OverlapGuardTest(unittest.TestCase):
    def test_apply_edits_skips_overlapping(self) -> None:
        from knot.core.writer import Edit, apply_edits

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "x.knot"
            path.write_text("一行\n二行\n三行\n", encoding="utf-8", newline="")
            apply_edits(
                path,
                [
                    Edit(2, 3, ["替换二三\n"]),
                    Edit(2, 2, ["被吞掉\n"]),  # 与上一个编辑相交 → 跳过
                ],
            )
            self.assertEqual(path.read_text(encoding="utf-8"), "一行\n替换二三\n")


if __name__ == "__main__":
    unittest.main()
