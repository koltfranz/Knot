from __future__ import annotations

import codecs
import tempfile
import unittest
from pathlib import Path

from knot.core.normalize import KnotError, read_text, sniff_and_read

LEDGER = "2026-01-01 open 资产:现金 CNY\n"


class EncodingTest(unittest.TestCase):
    def test_gb18030(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "微信账单.csv"
            path.write_bytes(LEDGER.encode("gb18030"))
            self.assertEqual(sniff_and_read(path), LEDGER)

    def test_utf8_with_bom(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "带BOM.knot"
            path.write_bytes(codecs.BOM_UTF8 + LEDGER.encode("utf-8"))
            self.assertEqual(sniff_and_read(path), LEDGER)
            self.assertEqual(read_text(path), LEDGER)

    def test_utf16(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "utf16.knot"
            path.write_bytes(LEDGER.encode("utf-16"))
            self.assertEqual(sniff_and_read(path).replace("\ufeff", ""), LEDGER)

    def test_undecodable_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "坏文件.bin"
            path.write_bytes(b"\xff\xff\xff\xff\xff")
            with self.assertRaises(KnotError):
                sniff_and_read(path)


if __name__ == "__main__":
    unittest.main()
