from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from knot.cli.main import main

LEDGER = """option "strict" "off"

2026-01-01 open 资产:现金 CNY

2026-01-05 * "外卖"  费用:餐饮:外卖  50.00 CNY  @ 资产:现金
"""

BROKEN = """2026-01-01 * "不平衡"
  费用:餐饮     10.00 CNY
  资产:现金     -8.00 CNY
"""


class DoctorTest(unittest.TestCase):
    def _run(self, *argv: str) -> tuple[int, str]:
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = main(list(argv))
        return code, buffer.getvalue()

    def test_doctor_ok_for_valid_ledger(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "main.knot"
            path.write_text(LEDGER, encoding="utf-8", newline="")
            code, output = self._run("--账本", str(path), "自检")
            self.assertEqual(code, 0)
            self.assertIn("Python", output)
            self.assertIn("账本", output)
            self.assertIn("失败 0", output)

    def test_doctor_fails_on_broken_ledger(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "main.knot"
            path.write_text(BROKEN, encoding="utf-8", newline="")
            code, _output = self._run("--账本", str(path), "自检")
            self.assertEqual(code, 1)

    def test_doctor_without_ledger_only_warns(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            code, output = self._run("--账本", str(Path(tmp) / "没有.knot"), "自检")
            self.assertEqual(code, 0)
            self.assertIn("警告", output)

    def test_doctor_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "main.knot"
            path.write_text(LEDGER, encoding="utf-8", newline="")
            code, output = self._run("--账本", str(path), "自检", "--json")
            self.assertEqual(code, 0)
            payload = json.loads(output)
            self.assertEqual(payload["失败"], 0)
            self.assertIn("版本", payload)
            self.assertTrue(any(item["项目"] == "Python" for item in payload["结果"]))


if __name__ == "__main__":
    unittest.main()
