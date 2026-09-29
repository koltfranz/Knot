from __future__ import annotations

import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from knot.cli.commands.demo import demo_commands, demo_root
from knot.cli.main import main
from knot.core.chart import (
    spec_budget_gauge,
    spec_calendar_heatmap,
    spec_cash_flow_waterfall,
    spec_category_treemap,
    spec_expense_pie,
    spec_monthly_flow,
    spec_net_worth,
)
from knot.core.loader import load_book

DEMO = demo_root()

CHART_COMMANDS = (
    ("图", "支出"),
    ("图", "净资产"),
    ("图", "分类"),
    ("图", "分类", "--类型", "树"),
    ("图", "日历"),
    ("图", "预算"),
    ("图", "现金流"),
)


class DemoLedgerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.ledger = DEMO / "main.knot"

    def test_demo_exists_and_is_valid(self) -> None:
        self.assertTrue(self.ledger.exists(), "缺少内置示例账本")
        _result, book, diags = load_book(self.ledger)
        self.assertEqual([d for d in diags if d.level == "error"], [])
        self.assertGreater(len(book.transactions), 200)

    def test_demo_covers_all_syntax(self) -> None:
        text = "\n".join(path.read_text(encoding="utf-8") for path in sorted(DEMO.rglob("*.knot")))
        for token in (
            "option",
            "include",
            "open",
            "close",
            "balance",
            "price",
            "commodity",
            "recur",
            "budget",
            "event",
            " ! ",
            " ? ",
            " P ",
            "#",
            "^",
            "{",
            "USD",
        ):
            self.assertIn(token, text, f"示例缺少语法点：{token}")
        readme = (DEMO / "README.md").read_text(encoding="utf-8")
        self.assertIn("鼠标", readme)

    def test_all_seven_charts_have_data(self) -> None:
        _result, book, _diags = load_book(self.ledger)
        year = max(tx.date.year for tx in book.transactions)
        specs = [
            spec_monthly_flow(book),
            spec_net_worth(book),
            spec_expense_pie(book),
            spec_category_treemap(book),
            spec_calendar_heatmap(book, year),
            spec_budget_gauge(book),
            spec_cash_flow_waterfall(book),
        ]
        self.assertEqual(len({spec.kind for spec in specs}), 7)
        for spec in specs:
            self.assertTrue(spec.labels, f"{spec.kind} 没有标签")
            self.assertTrue(any(series.values for series in spec.series), f"{spec.kind} 没有数据")

    def test_demo_reconciles_and_holds_investments(self) -> None:
        _result, book, _diags = load_book(self.ledger)
        from knot.core.inventory import build_positions

        positions = build_positions(book)
        self.assertTrue(positions, "示例应包含投资持仓")


class DemoCommandTest(unittest.TestCase):
    def _run(self, *argv: str) -> tuple[int, str]:
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = main(list(argv))
        return code, buffer.getvalue()

    def test_demo_command_copies_and_checks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "演示账本"
            code, output = self._run("示例", str(target))
            self.assertEqual(code, 0)
            self.assertIn("示例账本已就绪", output)
            self.assertTrue((target / "main.knot").exists())
            self.assertTrue((target / "规则" / "分类规则.knot").exists())

            code, _output = self._run("--账本", str(target / "main.knot"), "检查", "--静默")
            self.assertEqual(code, 0)

            code, output = self._run("示例", str(target))
            self.assertEqual(code, 0)
            self.assertIn("已存在，跳过", output)

    def test_demo_open_flag(self) -> None:
        """`示例 --打开`：复制后直接打开；非交互终端退回输出概况。"""
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "演示账本"
            code, output = self._run("示例", str(target), "--打开")
            self.assertEqual(code, 0)
            self.assertTrue((target / "main.knot").exists())
            self.assertIn("交易数：", output)
            self.assertIn("不是交互式终端", output)

    def test_printed_commands_are_runnable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "演示账本"
            code, output = self._run("示例", str(target))
            self.assertEqual(code, 0)
            self.assertEqual(len(demo_commands(target)), 13)
            for topic in ("图 支出", "图 净资产", "图 分类", "图 日历", "图 预算", "图 现金流"):
                self.assertIn(topic, output)

            ledger = str(target / "main.knot")
            for command in CHART_COMMANDS:
                code, _output = self._run("--账本", ledger, *command)
                self.assertEqual(code, 0, f"{' '.join(command)} 失败")
            for command in (("报", "概况"), ("余", "--树"), ("预算",), ("持仓",), ("定期",)):
                code, _output = self._run("--账本", ledger, *command)
                self.assertEqual(code, 0, f"{' '.join(command)} 失败")


if __name__ == "__main__":
    unittest.main()
