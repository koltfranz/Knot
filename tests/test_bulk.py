from __future__ import annotations

import csv
import json
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from knot.core.bulk import (
    delete_transactions,
    export_transactions,
    selectable,
    selection_key,
    summarize,
    tag_transactions,
)
from knot.core.loader import load_book

LEDGER = """option "strict" "off"

2026-01-01 open 资产:银行:招行 CNY
2026-01-01 open 资产:现金 CNY
2026-01-01 open 权益:期初

2026-01-05 * "腾讯" "工资"
  收入:工资      -8,000.00 CNY
  资产:银行:招行

2026-01-06 "外卖"  费用:餐饮:外卖  50.00 CNY  @ 资产:现金

2026-01-07 * "超市"
  费用:餐饮:食材     128.00 CNY
  费用:日用品         45.00 CNY
  资产:现金

2026-01-01 recur "monthly" "房租" from 2026-01-01 to 2026-02-01
  费用:居住:房租   3,000.00 CNY  @ 资产:银行:招行
"""


class BulkTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name) / "main.knot"
        self.path.write_text(LEDGER, encoding="utf-8", newline="")
        self.book = load_book(self.path)[1]

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _text(self) -> str:
        return self.path.read_text(encoding="utf-8")

    def _by_narration(self, name: str) -> list:
        return [tx for tx in self.book.transactions if tx.narration == name]

    def test_selectable_skips_generated_and_dedupes(self) -> None:
        picked, skipped = selectable(self.book.transactions)
        self.assertTrue(all("房租" not in (tx.narration or "") for tx in picked))
        self.assertGreaterEqual(skipped, 2)  # 两笔定期展开

        same = self._by_narration("外卖")
        picked, skipped = selectable([*same, *same])
        self.assertEqual(len(picked), 1)
        self.assertEqual(skipped, 1)

    def test_tag_transactions_keeps_other_lines(self) -> None:
        before = self.path.read_bytes().splitlines(keepends=True)
        target = self._by_narration("外卖")
        result = tag_transactions(target, ["报销", "#工作"])
        self.assertEqual(result.changed, 1)

        text = self._text()
        self.assertIn("#报销", text)
        self.assertIn("#工作", text)
        after = self.path.read_bytes().splitlines(keepends=True)
        changed = "外卖".encode()
        for line in before:
            if changed in line or b"50.00" in line:
                continue
            self.assertIn(line, after, "未编辑行字节不变")
        _result, _book, diags = load_book(self.path)
        self.assertEqual([d for d in diags if d.level == "error"], [])

    def test_tag_transactions_rejects_empty(self) -> None:
        from knot.core.normalize import KnotError

        with self.assertRaises(KnotError):
            tag_transactions(self._by_narration("外卖"), ["  ", "#"])

    def test_delete_transactions_backs_up_and_removes(self) -> None:
        original = self._text()
        result = delete_transactions(self._by_narration("外卖"))
        self.assertEqual(result.changed, 1)
        self.assertEqual(len(result.backups), 1)
        self.assertEqual(result.backups[0].read_text(encoding="utf-8"), original)

        text = self._text()
        self.assertNotIn("外卖", text)
        self.assertIn("超市", text)
        self.assertNotIn("\n\n\n", text)
        _result, _book, diags = load_book(self.path)
        self.assertEqual([d for d in diags if d.level == "error"], [])

    def test_delete_skips_generated(self) -> None:
        before = self._text()
        rent = [tx for tx in self.book.transactions if tx.narration == "房租"]
        result = delete_transactions(rent)
        self.assertEqual(result.changed, 0)
        self.assertEqual(result.skipped, len(rent))
        self.assertEqual(self._text(), before, "定期模板 MUST 不变")

    def test_summarize_counts_income_and_expense_only(self) -> None:
        selected = [*self._by_narration("工资"), *self._by_narration("外卖")]
        summary = summarize(selected)
        self.assertEqual(summary["笔数"], 2)
        self.assertEqual(summary["收支合计"]["CNY"], Decimal("8050.00"))

        opening = self._by_narration("期初")
        self.assertEqual(summarize(opening)["收支合计"], {})

    def test_export_csv_and_json(self) -> None:
        selected = [*self._by_narration("工资"), *self._by_narration("超市")]
        target = Path(self._tmp.name) / "导出.csv"
        count, path = export_transactions(selected, target, "csv")
        self.assertEqual(path, target)
        self.assertGreaterEqual(count, 3)
        with target.open(encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(rows[0]["科目"], "收入:工资")
        self.assertTrue(any(row["科目"] == "费用:日用品" for row in rows))

        target_json = Path(self._tmp.name) / "导出.json"
        count, _path = export_transactions(selected, target_json, "json")
        payload = json.loads(target_json.read_text(encoding="utf-8"))
        self.assertEqual(len(payload), count)
        self.assertIn("来源", payload[0])

    def test_selection_key_uses_file_and_line(self) -> None:
        keys = {selection_key(tx) for tx in self.book.transactions}
        # 两笔定期展开共享同一模板块 → 唯一键比交易数少 1
        self.assertEqual(len(keys), len(self.book.transactions) - 1)


if __name__ == "__main__":
    unittest.main()
