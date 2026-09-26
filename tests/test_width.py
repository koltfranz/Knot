from __future__ import annotations

import unittest

from knot.core.width import char_width, pad, str_width, truncate


class WidthTest(unittest.TestCase):
    def test_str_width(self) -> None:
        self.assertEqual(str_width("资产:银行"), 9)
        self.assertEqual(str_width("abc"), 3)
        self.assertEqual(str_width(""), 0)

    def test_char_width(self) -> None:
        self.assertEqual(char_width("资"), 2)
        self.assertEqual(char_width("a"), 1)
        self.assertEqual(char_width("\u0301"), 0)

    def test_pad_keeps_display_width(self) -> None:
        self.assertEqual(str_width(pad("资产", 10)), 10)
        self.assertEqual(str_width(pad("资产", 10, "right")), 10)
        self.assertEqual(pad("资产", 2), "资产")

    def test_truncate_keeps_hanzi_intact(self) -> None:
        text = truncate("资产:银行:招行", 8)
        self.assertTrue(text.endswith("…"))
        self.assertLessEqual(str_width(text), 8)
        self.assertNotIn("\ufffd", text)
        self.assertEqual(truncate("短期", 10), "短期")


if __name__ == "__main__":
    unittest.main()
