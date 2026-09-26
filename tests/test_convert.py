from __future__ import annotations

import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from knot.core.convert import (
    DIRECTION_TO_FULL,
    DIRECTION_TO_HALF,
    SCOPE_ALL,
    SCOPE_SYNTAX,
    convert_file,
    convert_text,
)
from knot.core.fmt import format_file
from knot.core.loader import load_book

DIRTY = """选项 "记账币种" "CNY"

2026-01-01 开立 资产：现金　CNY

2026-01-01 * “午饭”
  费用：餐饮　　38.00 CNY　＠资产：现金
"""

CLEAN = """选项 "记账币种" "CNY"

2026-01-01 开立 资产:现金 CNY

2026-01-01 * "午饭"
  费用:餐饮  38.00 CNY  @资产:现金
"""


class ConvertTest(unittest.TestCase):
    def test_syntax_scope_converts_fullwidth(self) -> None:
        report = convert_text(DIRTY, DIRECTION_TO_HALF, SCOPE_SYNTAX)
        self.assertIn("资产:现金", report.text)
        self.assertIn("费用:餐饮", report.text)
        self.assertIn("@资产:现金", report.text)
        self.assertNotIn("：", report.text)
        self.assertNotIn("　", report.text)
        self.assertIn('"午饭"', report.text)
        self.assertGreater(report.change_count, 0)

    def test_text_untouched_in_syntax_scope(self) -> None:
        text = '2026-01-01 * "午饭，加蛋"\n'
        report = convert_text(text, DIRECTION_TO_HALF, SCOPE_SYNTAX)
        self.assertIn("午饭，加蛋", report.text)

    def test_text_scope_converts_inside_strings(self) -> None:
        text = '2026-01-01 * "午饭，加蛋"\n'
        report = convert_text(text, DIRECTION_TO_HALF, SCOPE_ALL)
        self.assertIn("午饭,加蛋", report.text)

    def test_half_to_full_requires_text_scope(self) -> None:
        text = '2026-01-01 * "午饭, 加蛋"\n'
        report = convert_text(text, DIRECTION_TO_FULL, SCOPE_ALL)
        self.assertIn("午饭， 加蛋", report.text)
        self.assertIn('"', report.text)

    def test_half_to_full_keeps_decimal_point(self) -> None:
        text = '2026-01-01 * "花了 3.50 元, 还行"\n'
        report = convert_text(text, DIRECTION_TO_FULL, SCOPE_ALL)
        self.assertIn("3.50", report.text)
        self.assertIn("，", report.text)

    def test_idempotent(self) -> None:
        first = convert_text(DIRTY, DIRECTION_TO_HALF, SCOPE_SYNTAX)
        second = convert_text(first.text, DIRECTION_TO_HALF, SCOPE_SYNTAX)
        self.assertEqual(first.text, second.text)
        self.assertEqual(second.change_count, 0)

    def test_clean_text_needs_no_change(self) -> None:
        report = convert_text(CLEAN, DIRECTION_TO_HALF, SCOPE_SYNTAX)
        self.assertFalse(report.changed)
        self.assertEqual(report.text, CLEAN)

    def test_unclosed_string_reported_and_fixed(self) -> None:
        text = '2026-01-01 * "午饭\n  费用:餐饮  38.00 CNY  @资产:现金\n'
        report = convert_text(text, DIRECTION_TO_HALF, SCOPE_SYNTAX)
        self.assertEqual(report.unclosed_lines, [1])
        self.assertTrue(any("未闭合" in d.message for d in report.diagnostics))

        fixed = convert_text(text, DIRECTION_TO_HALF, SCOPE_SYNTAX, fix_unclosed=True)
        self.assertNotIn('"午饭\n', fixed.text)
        self.assertIn('"午饭"', fixed.text)

    def test_unbalanced_brace_reported_and_fixed(self) -> None:
        text = '2026-01-01 * "买入"\n  资产:投资 1000 FUND {3.85 CNY\n'
        report = convert_text(text, DIRECTION_TO_HALF, SCOPE_SYNTAX)
        self.assertEqual(report.unbalanced_lines, [2])

        fixed = convert_text(text, DIRECTION_TO_HALF, SCOPE_SYNTAX, fix_unclosed=True)
        self.assertIn("3.85 CNY}", fixed.text)

    def test_convert_file_writes_parseable_ledger(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "main.knot"
            path.write_text(DIRTY, encoding="utf-8")

            before = load_book(path)[2]
            self.assertTrue([d for d in before if d.level == "error"])

            report = convert_file(path, direction=DIRECTION_TO_HALF, scope=SCOPE_SYNTAX)
            self.assertTrue(report.changed)

            _result, _book, diags = load_book(path)
            self.assertEqual([d for d in diags if d.level == "error"], [])

            second = convert_file(path, direction=DIRECTION_TO_HALF, scope=SCOPE_SYNTAX)
            self.assertFalse(second.changed)

    def test_convert_file_dry_run_keeps_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "main.knot"
            path.write_text(DIRTY, encoding="utf-8")
            convert_file(path, direction=DIRECTION_TO_HALF, scope=SCOPE_SYNTAX, write=False)
            self.assertEqual(path.read_text(encoding="utf-8"), DIRTY)

    def test_crlf_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "main.knot"
            path.write_bytes("2026-01-01 * “午饭”\n".replace("\n", "\r\n").encode("utf-8"))
            convert_file(path, direction=DIRECTION_TO_HALF, scope=SCOPE_SYNTAX)
            raw = path.read_bytes()
            self.assertIn(b"\r\n", raw)
            self.assertNotIn(b"\n\n", raw.replace(b"\r\n", b""))

    def test_format_does_not_change_keyword_language(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "main.knot"
            source = (
                "2026-01-01 开立 资产:现金 CNY\n\n"
                '2026-01-02 * "午饭"\n'
                "  费用:餐饮   38.00 CNY  @资产:现金\n"
            )
            path.write_text(source, encoding="utf-8")
            format_file(path)
            self.assertIn("开立", path.read_text(encoding="utf-8"))

    def test_repairs_wild_ledger_from_test_data(self) -> None:
        source = Path(__file__).resolve().parents[1] / "schema" / "测试数据" / "全角脏账本.knot"
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "main.knot"
            path.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")

            _result, _book, diags = load_book(path)
            self.assertTrue([d for d in diags if d.level == "error"])

            convert_file(path, direction=DIRECTION_TO_HALF, scope=SCOPE_SYNTAX)
            _result, book, diags = load_book(path)
            self.assertEqual([d for d in diags if d.level == "error"], [])
            self.assertEqual(book.balance_of("资产:现金")["CNY"], Decimal("1000.00"))


if __name__ == "__main__":
    unittest.main()
