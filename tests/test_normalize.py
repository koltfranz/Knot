from __future__ import annotations

import unittest

from knot.core.normalize import normalize_currency, normalize_text


class NormalizeTest(unittest.TestCase):
    def test_fullwidth_punctuation(self) -> None:
        self.assertEqual(normalize_text("资产：现金"), "资产:现金")
        self.assertEqual(normalize_text("38，50"), "38,50")
        self.assertEqual(normalize_text("（备注）"), "(备注)")

    def test_fullwidth_digits_and_space(self) -> None:
        self.assertEqual(normalize_text("１２３"), "123")
        self.assertEqual(normalize_text("资产　现金"), "资产 现金")

    def test_currency_symbols(self) -> None:
        self.assertEqual(normalize_text("￥38"), "¥38")
        self.assertEqual(normalize_currency("￥"), "CNY")
        self.assertEqual(normalize_currency("元"), "CNY")
        self.assertEqual(normalize_currency("块"), "CNY")
        self.assertEqual(normalize_currency("美元"), "USD")
        self.assertEqual(normalize_currency("cny"), "CNY")

    def test_translate_before_nfkc(self) -> None:
        self.assertEqual(normalize_text("；"), ";")
        self.assertEqual(normalize_text("￥38"), "¥38")


if __name__ == "__main__":
    unittest.main()
