from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from decimal import Decimal
from pathlib import Path

from knot.cli.main import main
from knot.core.importer import alipay, bank, wechat
from knot.core.importer.base import (
    ImportRow,
    parse_money,
    split_duplicates,
)
from knot.core.loader import load_book

DATA = Path(__file__).resolve().parents[1] / "schema" / "测试数据" / "导入"


class ParserTest(unittest.TestCase):
    def test_wechat(self) -> None:
        result = wechat.parse(DATA / "微信.csv")
        self.assertEqual([d for d in result.diagnostics if d.level == "error"], [])
        self.assertEqual(len(result.rows), 5)
        first = result.rows[0]
        self.assertEqual(first.date.isoformat(), "2026-09-01")
        self.assertEqual(first.amount, Decimal("32.00"))
        self.assertEqual(first.direction, "支出")
        self.assertEqual(first.payee, "星巴克")

        income_row = next(row for row in result.rows if row.direction == "收入")
        self.assertEqual(income_row.amount, Decimal("66.00"))
        self.assertFalse(any(row.raw[4] == "不计收支" for row in result.rows))

    def test_alipay_gbk(self) -> None:
        text = (DATA / "支付宝.csv").read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "支付宝.csv"
            path.write_bytes(text.encode("gbk"))
            result = alipay.parse(path)
        self.assertEqual([d for d in result.diagnostics if d.level == "error"], [])
        self.assertEqual(len(result.rows), 4)
        self.assertEqual(result.rows[0].payee, "肯德基")
        self.assertEqual(result.rows[0].amount, Decimal("24.00"))
        self.assertEqual(result.rows[2].direction, "收入")

    def test_bank_split_columns(self) -> None:
        result = bank.parse(DATA / "银行.csv")
        self.assertEqual([d for d in result.diagnostics if d.level == "error"], [])
        self.assertEqual(len(result.rows), 5)
        self.assertEqual(result.rows[0].direction, "收入")
        self.assertEqual(result.rows[0].amount, Decimal("18000.00"))
        self.assertEqual(result.rows[1].direction, "支出")
        self.assertEqual(result.rows[1].amount, Decimal("3500.00"))
        self.assertEqual(result.rows[1].payee, "某房东")

    def test_missing_header_is_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "随便.csv"
            path.write_text("a,b,c\n1,2,3\n", encoding="utf-8")
            result = wechat.parse(path)
        self.assertTrue(any(d.level == "error" for d in result.diagnostics))

    def test_parse_money(self) -> None:
        self.assertEqual(parse_money("¥32.00"), Decimal("32.00"))
        self.assertEqual(parse_money("1,234.56"), Decimal("1234.56"))
        self.assertEqual(parse_money("-38.00"), Decimal("-38.00"))
        self.assertEqual(parse_money("38.00元"), Decimal("38.00"))
        self.assertIsNone(parse_money("无"))

    def test_split_duplicates_with_ordinals(self) -> None:
        row = ImportRow(
            date=parse_d("2026-09-01"), amount=Decimal("32.00"), direction="支出", payee="星巴克"
        )
        known = {("2026-09-01", "32.00", "星巴克"): 1}
        kept, duplicates = split_duplicates([row, row], known)
        self.assertEqual(len(kept), 1)

        kept, duplicates = split_duplicates([row], known)
        self.assertEqual(kept, [])
        self.assertEqual(len(duplicates), 1)


def parse_d(text: str):
    from datetime import date

    return date.fromisoformat(text)


class ImportCommandTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.ledger = Path(self._tmp.name) / "main.knot"
        self.ledger.write_text(
            'option "strict" "off"\n'
            'option "default_asset" "资产:银行:招行"\n'
            "\n"
            "2026-01-01 open 资产:银行:招行 CNY\n",
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _run(self, *argv: str) -> tuple[int, str]:
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = main(["--账本", str(self.ledger), *argv])
        return code, buffer.getvalue()

    def test_dry_run_does_not_write(self) -> None:
        before = self.ledger.read_text(encoding="utf-8")
        code, output = self._run("导入", "微信", str(DATA / "微信.csv"), "--试运行")
        self.assertEqual(code, 0)
        self.assertIn("试运行", output)
        self.assertIn("可导入 5", output)
        self.assertEqual(self.ledger.read_text(encoding="utf-8"), before)

    def test_import_writes_and_dedupes(self) -> None:
        code, output = self._run("导入", "微信", str(DATA / "微信.csv"))
        self.assertEqual(code, 0)
        self.assertIn("已导入", output)

        _result, _book, diags = load_book(self.ledger)
        self.assertEqual([d for d in diags if d.level == "error"], [])
        text = self.ledger.read_text(encoding="utf-8")
        self.assertIn("星巴克", text)
        self.assertIn("费用:待分类", text)

        code, output = self._run("导入", "微信", str(DATA / "微信.csv"))
        self.assertEqual(code, 0)
        self.assertIn("重复 5", output)
        self.assertIn("可导入 0", output)

    def test_import_with_rule_matching(self) -> None:
        rules = self.ledger.parent / "规则"
        rules.mkdir(parents=True, exist_ok=True)
        (rules / "分类规则.knot").write_text("星巴克 = 费用:餐饮:咖啡\n", encoding="utf-8")
        self.ledger.write_text(
            self.ledger.read_text(encoding="utf-8").replace(
                'option "strict" "off"\n',
                'option "strict" "off"\ninclude "规则/分类规则.knot"\n',
            ),
            encoding="utf-8",
        )

        code, output = self._run("导入", "微信", str(DATA / "微信.csv"))
        self.assertEqual(code, 0)
        self.assertIn("待分类 4", output)
        text = self.ledger.read_text(encoding="utf-8")
        self.assertIn("费用:餐饮:咖啡", text)

    def test_json_output(self) -> None:
        code, output = self._run("导入", "银行", str(DATA / "银行.csv"), "--试运行", "--json")
        self.assertEqual(code, 0)
        payload = json.loads(output)
        stats = next(iter(payload.values()))
        self.assertEqual(stats["可导入"], 5)

    def test_unknown_source(self) -> None:
        code, _output = self._run("导入", "某银行", str(DATA / "银行.csv"))
        self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
