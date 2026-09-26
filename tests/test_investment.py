from __future__ import annotations

import tempfile
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path

from knot.core.book import build
from knot.core.inventory import (
    METHOD_AVERAGE,
    build_positions,
    convert,
    latest_price,
    net_worth_in,
)
from knot.core.model import Options
from knot.core.parser import Parser
from knot.core.sql import execute, parse

LEDGER = """option "strict" "off"

2026-01-01 open 资产:银行:招行 CNY
2026-01-01 open 资产:投资:沪深300 FUND
2026-01-01 open 权益:期初

2026-01-01 * "期初"
  资产:银行:招行     100,000.00 CNY
  权益:期初

2026-02-01 * "买入"
  资产:投资:沪深300     1000 FUND {3.8500 CNY}
  资产:银行:招行      -3,850.00 CNY

2026-03-01 * "再加仓"
  资产:投资:沪深300     500 FUND {4.2000 CNY}
  资产:银行:招行      -2,100.00 CNY

2026-04-01 * "卖出"
  资产:投资:沪深300     -600 FUND {5.0000 CNY}
  资产:银行:招行      3,000.00 CNY

2026-06-01 price FUND 4.1200 CNY
2026-06-01 price USD 7.1000 CNY
"""


def build_book(text: str = LEDGER):
    directives, _diags = Parser(text, "test.knot").parse()
    book, _book_diags = build(directives, Options(strict="off"), {"test.knot": text.splitlines()})
    return book


class InventoryTest(unittest.TestCase):
    def test_fifo_position(self) -> None:
        book = build_book()
        positions = build_positions(book)
        self.assertEqual(len(positions), 1)
        position = positions[0]
        self.assertEqual(position.commodity, "FUND")
        self.assertEqual(position.units, Decimal("900.0000"))
        # 卖出 600 消耗最早一批 3.8500 → 剩余成本 = 1000*3.85 - 600*3.85 + 500*4.2 = 3640
        self.assertEqual(position.cost_total, Decimal("3640.00000"))
        self.assertEqual(position.market_price, Decimal("4.1200"))
        self.assertEqual(position.market_value, Decimal("3708.000000"))
        self.assertEqual(position.unrealized, Decimal("68.000000"))
        # 已实现：卖出 600 得 3000，成本 600*3.85 = 2310 → 690
        self.assertEqual(position.realized, Decimal("690.000000"))

    def test_average_position(self) -> None:
        book = build_book()
        position = build_positions(book, method=METHOD_AVERAGE)[0]
        self.assertEqual(position.units, Decimal("900.0000"))
        # 平均成本：(3850 + 2100) / 1500 = 3.9666…；卖出 600 → 剩余成本 3570
        self.assertEqual(position.cost_total.quantize(Decimal("0.01")), Decimal("3570.00"))
        self.assertEqual(position.realized.quantize(Decimal("0.01")), Decimal("620.00"))

    def test_latest_price_and_convert(self) -> None:
        book = build_book()
        self.assertEqual(latest_price(book, "FUND"), Decimal("4.1200"))
        self.assertIsNone(latest_price(book, "FUND", when=date(2026, 1, 1)))
        self.assertEqual(convert(book, Decimal("100"), "USD", "CNY"), Decimal("710.0000"))
        self.assertEqual(
            convert(book, Decimal("710"), "CNY", "USD").quantize(Decimal("0.01")), Decimal("100.00")
        )
        self.assertEqual(convert(book, Decimal("5"), "CNY", "CNY"), Decimal("5"))

    def test_net_worth_in_operating_currency(self) -> None:
        book = build_book()
        outcome = net_worth_in(book)
        self.assertEqual(outcome["币种"], "CNY")
        # 现金 100000 - 3850 - 2100 + 3000 = 97050；持仓市值 900 * 4.12 = 3708
        self.assertEqual(outcome["折算后"], Decimal("100758.000000"))
        self.assertEqual(outcome["缺报价"], {})


class SqlTest(unittest.TestCase):
    def test_parse_and_select(self) -> None:
        book = build_book()
        outcome = execute(book, "SELECT 日期, 科目, 金额 FROM 分录 WHERE 科目 包含 投资")
        self.assertEqual(outcome["条数"], 3)
        self.assertEqual(outcome["字段"], ["日期", "科目", "金额"])

    def test_conditions_numeric(self) -> None:
        book = build_book()
        outcome = execute(book, "SELECT 日期, 金额 FROM 分录 WHERE 金额 >= 3000 AND 科目 包含 银行")
        self.assertEqual(outcome["条数"], 2)
        outcome = execute(book, "SELECT 日期 FROM 分录 WHERE 金额 > 3000 AND 科目 包含 银行")
        self.assertEqual(outcome["条数"], 1)

    def test_aggregate_and_group(self) -> None:
        book = build_book()
        outcome = execute(book, "SELECT 合计(金额) FROM 分录 GROUP BY 科目")
        grouped = {row[0]: row[1] for row in outcome["行"]}
        self.assertIn("资产:银行:招行", grouped)
        self.assertEqual(grouped["资产:银行:招行"], "97,050.00")

    def test_order_and_limit(self) -> None:
        book = build_book()
        outcome = execute(
            book, "SELECT 日期, 金额 FROM 分录 WHERE 金额 > 0 ORDER BY 金额 DESC LIMIT 2"
        )
        self.assertEqual(outcome["条数"], 2)
        self.assertEqual(outcome["行"][0][1], "100,000.00")

    def test_transaction_source(self) -> None:
        book = build_book()
        outcome = execute(book, "SELECT 日期, 摘要, 标签 FROM 流水 WHERE 摘要 包含 买入")
        self.assertEqual(outcome["条数"], 1)

    def test_errors(self) -> None:
        from knot.core.normalize import KnotError

        book = build_book()
        with self.assertRaises(KnotError):
            parse("DELETE FROM 流水")
        with self.assertRaises(KnotError):
            execute(book, "SELECT 日期 FROM 未知源")
        with self.assertRaises(KnotError):
            execute(book, "SELECT 不存在的字段 FROM 分录")


class HoldingsCommandTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.ledger = Path(self._tmp.name) / "main.knot"
        self.ledger.write_text(LEDGER, encoding="utf-8")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _run(self, *argv: str) -> tuple[int, str]:
        import io
        from contextlib import redirect_stdout

        from knot.cli.main import main

        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = main(["--账本", str(self.ledger), *argv])
        return code, buffer.getvalue()

    def test_holdings_command(self) -> None:
        code, output = self._run("持仓")
        self.assertEqual(code, 0)
        self.assertIn("沪深300", output)
        self.assertIn("4.1200", output)
        self.assertIn("净资产折算", output)

    def test_holdings_average_and_json(self) -> None:
        code, output = self._run("持仓", "--方法", "平均", "--json")
        self.assertEqual(code, 0)
        import json

        payload = json.loads(output)
        self.assertEqual(payload["方法"], "average")
        self.assertEqual(payload["持仓"][0]["商品"], "FUND")

    def test_show_sql(self) -> None:
        code, output = self._run("查", "--sql", "SELECT 合计(金额) FROM 分录 GROUP BY 科目")
        self.assertEqual(code, 0)
        self.assertIn("资产:银行:招行", output)

    def test_show_sql_json(self) -> None:
        code, output = self._run(
            "查", "--sql", "SELECT 日期, 科目, 金额 FROM 分录 WHERE 科目 包含 投资", "--json"
        )
        self.assertEqual(code, 0)
        import json

        payload = json.loads(output)
        self.assertEqual(payload["条数"], 3)


if __name__ == "__main__":
    unittest.main()
