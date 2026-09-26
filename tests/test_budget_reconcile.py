from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import date
from decimal import Decimal
from pathlib import Path

from knot.cli.main import main
from knot.core.actions import resolve_account
from knot.core.aliases import AliasTable
from knot.core.book import build
from knot.core.budget import rows as budget_rows
from knot.core.budget import summary as budget_summary
from knot.core.chart import render_svg, spec_budget_gauge
from knot.core.model import Options
from knot.core.parser import Parser
from knot.core.reconcile import mark_cleared, reconcile, write_assertion

LEDGER = """option "strict" "off"

2026-01-01 open 资产:银行:招行 CNY
2026-01-01 open 费用:餐饮:外卖 CNY
2026-01-01 open 权益:期初

2026-01-01 * "期初"
  资产:银行:招行     10,000.00 CNY
  权益:期初

2026-01-01 budget monthly 费用:餐饮 500.00 CNY

2026-01-05 * "外卖"  费用:餐饮:外卖  120.00 CNY  @ 资产:银行:招行
2026-02-06 * "外卖"  费用:餐饮:外卖  600.00 CNY  @ 资产:银行:招行
2026-02-10 * "工资"  收入:工资  -8,000.00 CNY  @ 资产:银行:招行
"""


def build_book(text: str = LEDGER, filename: str = "test.knot"):
    directives, _diags = Parser(text, filename).parse()
    book, _book_diags = build(directives, Options(strict="off"), {filename: text.splitlines()})
    return book


class BudgetTest(unittest.TestCase):
    def test_rows_and_progress(self) -> None:
        book = build_book()
        january = budget_rows(book, "2026-01")[0]
        self.assertEqual(january["实际"], Decimal("120.00"))
        self.assertEqual(january["剩余"], Decimal("380.00"))
        self.assertFalse(january["超支"])

        february = budget_rows(book, "2026-02")[0]
        self.assertEqual(february["实际"], Decimal("600.00"))
        self.assertTrue(february["超支"])

    def test_default_month_is_latest(self) -> None:
        book = build_book()
        self.assertEqual(budget_rows(book)[0]["月份"], "2026-02")

    def test_summary(self) -> None:
        book = build_book()
        total = budget_summary(book, "2026-02")
        self.assertEqual(total["预算合计"], Decimal("500.00"))
        self.assertEqual(total["实际合计"], Decimal("600.00"))
        self.assertEqual(total["超支科目"], ["费用:餐饮"])

    def test_gauge_spec_and_svg(self) -> None:
        book = build_book()
        spec = spec_budget_gauge(book, "2026-02")
        self.assertEqual(spec.kind, "gauge")
        self.assertEqual(spec.labels, ["费用:餐饮"])
        svg = render_svg(spec)
        self.assertIn("<svg", svg)
        self.assertIn("预算进度", svg)


class ReconcileTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name) / "main.knot"
        self.path.write_text(LEDGER, encoding="utf-8")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _book(self):
        from knot.core.loader import load_book

        return load_book(self.path)[1]

    def test_report_without_statement(self) -> None:
        report = reconcile(self._book(), "资产:银行:招行")
        self.assertEqual(report.cleared, 0)
        self.assertGreater(len(report.pending), 0)
        self.assertIn(
            "账本余额", __import__("knot.core.reconcile", fromlist=["x"]).render_report(report)
        )

    def test_difference_and_balanced(self) -> None:
        book = self._book()
        balance = book.balance_of("资产:银行:招行")["CNY"]
        report = reconcile(book, "资产:银行:招行", balance)
        self.assertTrue(report.balanced)
        self.assertIn("账实相符", report.suggestion)

        off = reconcile(book, "资产:银行:招行", balance + Decimal("100"))
        self.assertFalse(off.balanced)
        self.assertEqual(off.difference, Decimal("100"))

    def test_mark_cleared_writes_flag(self) -> None:
        book = self._book()
        report = reconcile(book, "资产:银行:招行")
        count = mark_cleared(report.pending)
        self.assertGreater(count, 0)
        text = self.path.read_text(encoding="utf-8")
        self.assertIn(" P ", text)

        again = reconcile(self._book(), "资产:银行:招行")
        self.assertEqual(len(again.pending), 0)
        self.assertGreater(again.cleared, 0)

    def test_write_assertion(self) -> None:
        book = self._book()
        assertion = __import__("knot.core.reconcile", fromlist=["x"]).balance_assertion(
            book, "资产:银行:招行", Decimal("17280.00"), date(2026, 3, 31)
        )
        target = write_assertion(self.path, assertion, [self.path])
        text = target.read_text(encoding="utf-8")
        self.assertIn("balance 资产:银行:招行 17,280.00 CNY", text)

        from knot.core.loader import load_book

        _result, _book, diags = load_book(self.path)
        self.assertEqual([d for d in diags if d.level == "error"], [])


class PinyinResolutionTest(unittest.TestCase):
    def test_resolve_by_pinyin(self) -> None:
        table = AliasTable()
        book = build_book()
        accounts = book.used_accounts()
        self.assertEqual(resolve_account(table, "zhaohang", "科目", accounts), "资产:银行:招行")
        self.assertEqual(resolve_account(table, "xianjin", "科目", accounts), "资产:现金")
        self.assertEqual(resolve_account(table, "fycywm", "科目", accounts), "费用:餐饮:外卖")

    def test_ambiguous_pinyin_returns_candidates(self) -> None:
        table = AliasTable()
        accounts = build_book().used_accounts()
        resolution = table.resolve("fycy", accounts)
        self.assertIsNone(resolution.target)
        self.assertIn("费用:餐饮", resolution.candidates)
        self.assertIn("费用:餐饮:外卖", resolution.candidates)

    def test_unknown_pinyin(self) -> None:
        table = AliasTable()
        resolution = table.resolve("zzzz", ["资产:现金"])
        self.assertIsNone(resolution.target)
        self.assertEqual(resolution.candidates, [])


class BudgetCommandTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.ledger = Path(self._tmp.name) / "main.knot"
        self.ledger.write_text(LEDGER, encoding="utf-8")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _run(self, *argv: str) -> tuple[int, str]:
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = main(["--账本", str(self.ledger), *argv])
        return code, buffer.getvalue()

    def test_budget_command(self) -> None:
        code, output = self._run("预算", "--月", "2026-02")
        self.assertEqual(code, 0)
        self.assertIn("费用:餐饮", output)
        self.assertIn("超支", output)

    def test_budget_json(self) -> None:
        code, output = self._run("预算", "--月", "2026-01", "--json")
        self.assertEqual(code, 0)
        payload = json.loads(output)
        self.assertEqual(payload["进度"][0]["实际"], "120.00")

    def test_recur_command(self) -> None:
        self.ledger.write_text(
            LEDGER + '\n2026-01-01 recur "monthly" "房租" from 2026-01-01 to 2026-03-01\n'
            "  费用:居住:房租 3,000.00 CNY  @ 资产:银行:招行\n",
            encoding="utf-8",
        )
        code, output = self._run("定期", "--月", "2026-02")
        self.assertEqual(code, 0)
        self.assertIn("monthly", output)
        self.assertIn("房租", output)

    def test_reconcile_command(self) -> None:
        code, output = self._run("对账", "招行")
        self.assertEqual(code, 0)
        self.assertIn("账本余额", output)

        code, _output = self._run("对账", "招行", "--余额", "1.00")
        self.assertEqual(code, 1)

    def test_reconcile_mark_and_assert(self) -> None:
        code, output = self._run("对账", "招行", "--余额", "17,280.00", "--标记", "--断言")
        self.assertEqual(code, 0)
        self.assertIn("已标记", output)
        text = self.ledger.read_text(encoding="utf-8")
        self.assertIn("balance 资产:银行:招行 17,280.00 CNY", text)

    def test_alias_test_command(self) -> None:
        code, output = self._run("别名", "测试", "xianjin")
        self.assertEqual(code, 0)
        self.assertIn("资产:现金", output)

    def test_alias_list_all(self) -> None:
        code, output = self._run("别名", "列表", "--全部")
        self.assertEqual(code, 0)
        self.assertIn("招行", output)

    def test_chart_budget(self) -> None:
        code, output = self._run("图", "预算", "--月", "2026-02")
        self.assertEqual(code, 0)
        self.assertIn("<svg", output)


if __name__ == "__main__":
    unittest.main()
