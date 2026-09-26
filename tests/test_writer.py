from __future__ import annotations

import tempfile
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path

from knot.core.model import Amount, Flag, Posting, Transaction
from knot.core.writer import Edit, apply_edits, insert_transaction, render_transaction

BASE = """option "operating_currency" "CNY"

2026-01-10 "早饭"
  费用:餐饮  8.00 CNY  @ 资产:现金

2026-03-10 "午饭"
  费用:餐饮  12.00 CNY  @ 资产:现金
"""


def make_tx(when: date, note: str, amount: str = "38.00") -> Transaction:
    return Transaction(
        date=when,
        flag=Flag.OK,
        payee=None,
        narration=note,
        postings=[
            Posting(
                account="费用:餐饮",
                units=Amount(Decimal(amount), "CNY"),
                counterparty="资产:现金",
            )
        ],
    )


class WriterTest(unittest.TestCase):
    def _write(self, tmp: str, text: str = BASE, newline: str = "\n") -> Path:
        path = Path(tmp) / "main.knot"
        path.write_text(text.replace("\n", newline), encoding="utf-8", newline="")
        return path

    def test_apply_edits_replace_and_insert(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write(tmp)
            apply_edits(
                path,
                [
                    Edit(2, 2, ['2026-01-10 "早饭"\n']),
                    Edit(6, 5, ['\n2026-02-10 "新"\n  费用:餐饮  1.00 CNY  @ 资产:现金\n']),
                ],
            )
            lines = path.read_text(encoding="utf-8").splitlines()
            self.assertEqual(lines[1], '2026-01-10 "早饭"')
            self.assertEqual(lines[4], "")
            self.assertEqual(lines[6], '2026-02-10 "新"')

    def test_insert_keeps_other_lines_untouched(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write(tmp)
            before = path.read_bytes()
            insert_transaction(path, make_tx(date(2026, 2, 15), "插入"))
            after = path.read_bytes()
            for line in before.splitlines(keepends=True):
                self.assertIn(line, after)
            self.assertIn(b"2026-02-15", after)

    def test_insert_position_by_date(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write(tmp)
            insert_transaction(path, make_tx(date(2026, 2, 15), "中间"))
            text = path.read_text(encoding="utf-8")
            self.assertLess(text.index("2026-01-10"), text.index("2026-02-15"))
            self.assertLess(text.index("2026-02-15"), text.index("2026-03-10"))

            insert_transaction(path, make_tx(date(2026, 12, 31), "末尾"))
            text = path.read_text(encoding="utf-8")
            self.assertLess(text.index("2026-03-10"), text.index("2026-12-31"))

    def test_block_separation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write(tmp)
            insert_transaction(path, make_tx(date(2026, 2, 15), "中间"))
            text = path.read_text(encoding="utf-8")
            self.assertIn('@ 资产:现金\n\n2026-02-15 "中间"', text)
            self.assertIn(
                '2026-02-15 "中间"\n  费用:餐饮  38.00 CNY  @ 资产:现金\n\n2026-03-10', text
            )

    def test_crlf_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write(tmp, newline="\r\n")
            insert_transaction(path, make_tx(date(2026, 2, 15), "插入"))
            raw = path.read_bytes()
            self.assertIn(b"2026-02-15", raw)
            self.assertIn(b"\r\n", raw)
            self.assertNotIn(b"\n", raw.replace(b"\r\n", b""))
            self.assertIn("\r\n", path.read_bytes().decode("utf-8"))

    def test_create_missing_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "2026.knot"
            insert_transaction(path, make_tx(date(2026, 2, 15), "新建"))
            self.assertTrue(path.exists())
            self.assertIn("2026-02-15", path.read_text(encoding="utf-8"))

    def test_render_alignment_and_generated_skipped(self) -> None:
        tx = Transaction(
            date=date(2026, 1, 1),
            flag=Flag.PENDING,
            payee=None,
            narration="对齐",
            postings=[
                Posting(account="费用:餐饮:早餐", units=Amount(Decimal("8.5"), "CNY")),
                Posting(account="资产:现金", units=Amount(Decimal("-8.5"), "CNY"), generated=True),
            ],
            tags=frozenset({"早餐"}),
        )
        lines = render_transaction(tx)
        self.assertTrue(lines[0].startswith('2026-01-01 ! "对齐" #早餐'))
        self.assertEqual(len(lines), 2)
        self.assertIn("8.50 CNY", lines[1])
        self.assertNotIn("资产:现金", "".join(lines))


if __name__ == "__main__":
    unittest.main()
