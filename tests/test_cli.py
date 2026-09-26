from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from knot.cli.main import main


class CliTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.ledger = Path(self._tmp.name) / "main.knot"

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _run(self, *argv: str) -> int:
        with redirect_stdout(io.StringIO()):
            return main(["--账本", str(self.ledger), *argv])

    def _run_capture(self, *argv: str) -> tuple[int, str]:
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = main(["--账本", str(self.ledger), *argv])
        return code, buffer.getvalue()

    def test_expense_writes_positive_posting(self) -> None:
        self.assertEqual(
            self._run("记", "38", "餐饮", "-f", "现金", "-n", "午饭", "-d", "2026-09-20"), 0
        )
        text = self.ledger.read_text(encoding="utf-8")
        self.assertIn('2026-09-20 "午饭"', text)
        self.assertIn("费用:餐饮", text)
        self.assertIn("38.00 CNY  @ 资产:现金", text)

    def test_income_signs_are_negated(self) -> None:
        self.assertEqual(self._run("记", "5000", "工资", "-t", "招行", "-d", "2026-09-21"), 0)
        text = self.ledger.read_text(encoding="utf-8")
        self.assertIn("收入:工资", text)
        self.assertIn("-5,000.00 CNY  @ 资产:银行:招行", text)

    def test_transfer_direction(self) -> None:
        self._run("记", "500", "资产:现金", "-f", "招行", "-d", "2026-09-20")
        self.assertIn("500.00 CNY  @ 资产:银行:招行", self.ledger.read_text(encoding="utf-8"))

        other = Path(self._tmp.name) / "转出.knot"
        with redirect_stdout(io.StringIO()):
            main(["--账本", str(other), "记", "500", "资产:现金", "-t", "招行", "-d", "2026-09-20"])
        self.assertIn("-500.00 CNY  @ 资产:银行:招行", other.read_text(encoding="utf-8"))

    def test_chinese_number_and_date(self) -> None:
        self.assertEqual(self._run("记", "2万3", "房租", "-f", "招行", "-d", "2026-09-22"), 0)
        self.assertIn("23,000.00 CNY", self.ledger.read_text(encoding="utf-8"))

    def test_check_exit_codes(self) -> None:
        self._run("记", "38", "餐饮", "-f", "现金", "-d", "2026-09-20")
        self.assertEqual(self._run("检查", "--静默"), 0)

        with self.ledger.open("a", encoding="utf-8", newline="") as fh:
            fh.write(
                '\n2026-09-30 * "不平衡"\n  费用:餐饮     10.00 CNY\n  资产:现金     -8.00 CNY\n'
            )
        self.assertEqual(self._run("检查", "--静默"), 1)
        self.assertEqual(self._run("查"), 1)

    def test_missing_ledger(self) -> None:
        self.assertEqual(self._run("余"), 1)
        self.assertEqual(self._run("记", "38", "餐饮", "-f", "现金", "-d", "2026-09-20"), 0)
        self.assertTrue(self.ledger.exists())

    def test_bal_tree_and_json(self) -> None:
        self._run("记", "38", "餐饮", "-f", "现金", "-d", "2026-09-20")
        code, output = self._run_capture("余", "--json")
        self.assertEqual(code, 0)
        payload = json.loads(output)
        self.assertEqual(payload["资产:现金"]["CNY"], "-38.00")

        code, output = self._run_capture("余", "--树", "--深度", "1")
        self.assertEqual(code, 0)
        self.assertIn("资产", output)

    def test_show_json_fields(self) -> None:
        self._run(
            "记", "38", "餐饮", "-f", "现金", "-n", "午饭", "--标签", "工作", "-d", "2026-09-20"
        )
        code, output = self._run_capture("查", "--标签", "工作", "--json")
        self.assertEqual(code, 0)
        records = json.loads(output)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["摘要"], "午饭")
        self.assertEqual(records[0]["标签"], ["工作"])

    def test_alias_add_list_remove(self) -> None:
        self.assertEqual(self._run("别名", "添加", "星巴克", "费用:餐饮:咖啡"), 0)
        code, output = self._run_capture("别名", "列表")
        self.assertEqual(code, 0)
        self.assertIn("星巴克", output)
        self.assertEqual(self._run("别名", "删除", "星巴克"), 0)
        self.assertEqual(self._run("别名", "删除", "星巴克"), 2)

    def test_alias_rejects_bad_target(self) -> None:
        self.assertEqual(self._run("别名", "添加", "咖啡", "随便写写"), 2)

    def test_fmt_is_idempotent(self) -> None:
        self._run("记", "38", "餐饮", "-f", "现金", "-d", "2026-09-20")
        self.assertEqual(self._run("整理"), 0)
        self.assertEqual(self._run("整理", "--检查"), 0)
        self.assertEqual(self._run("检查", "--静默"), 0)

    def test_completion_and_version(self) -> None:
        code, output = self._run_capture("--补全", "bash")
        self.assertEqual(code, 0)
        self.assertIn("complete", output)
        with self.assertRaises(SystemExit) as ctx:
            self._run_capture("--version")
        self.assertEqual(ctx.exception.code, 0)


if __name__ == "__main__":
    unittest.main()
