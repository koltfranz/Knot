from __future__ import annotations

import unittest

from tests import golden


class GoldenTest(unittest.TestCase):
    def test_golden(self) -> None:
        self.assertTrue(golden.CASES, "未找到黄金测试用例")
        for ledger_path in golden.CASES:
            with self.subTest(case=ledger_path.name):
                expected, book, diags = golden.run_case(ledger_path)

                if "错误行" in expected:
                    self.assertEqual(
                        golden.error_lines(diags), expected["错误行"], ledger_path.name
                    )
                    self.assertEqual(
                        golden.error_count(diags), expected["错误数"], ledger_path.name
                    )
                    self.assertEqual(book.summary()["交易数"], expected["交易数"], ledger_path.name)
                    continue

                self.assertEqual([d for d in diags if d.level == "error"], [], ledger_path.name)
                self.assertEqual(book.summary(), expected, ledger_path.name)


if __name__ == "__main__":
    unittest.main()
