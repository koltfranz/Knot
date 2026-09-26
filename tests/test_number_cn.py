from __future__ import annotations

import unittest
from decimal import Decimal

from knot.core.number_cn import parse_amount


class NumberCnTest(unittest.TestCase):
    def test_plain(self) -> None:
        self.assertEqual(parse_amount("38"), Decimal("38"))
        self.assertEqual(parse_amount("38.5"), Decimal("38.5"))
        self.assertEqual(parse_amount("1,234.56"), Decimal("1234.56"))
        self.assertEqual(parse_amount("-173.00"), Decimal("-173.00"))

    def test_units(self) -> None:
        self.assertEqual(parse_amount("3千"), Decimal("3000"))
        self.assertEqual(parse_amount("1.5万"), Decimal("15000"))
        self.assertEqual(parse_amount("3k"), Decimal("3000"))
        self.assertEqual(parse_amount("1.5w"), Decimal("15000"))

    def test_remainder_rule(self) -> None:
        self.assertEqual(parse_amount("2万3"), Decimal("23000"))
        self.assertEqual(parse_amount("3千5"), Decimal("3500"))
        self.assertEqual(parse_amount("1亿2千万"), Decimal("120000000"))

    def test_currency_words(self) -> None:
        self.assertEqual(parse_amount("38元"), Decimal("38"))
        self.assertEqual(parse_amount("¥38"), Decimal("38"))
        self.assertEqual(parse_amount("38块5"), Decimal("38.5"))
        self.assertEqual(parse_amount("3千5元"), Decimal("3500"))
        self.assertEqual(parse_amount("人民币 100"), Decimal("100"))

    def test_errors(self) -> None:
        with self.assertRaises(ValueError):
            parse_amount("")
        with self.assertRaises(ValueError):
            parse_amount("abc")
        with self.assertRaises(ValueError):
            parse_amount("38xyz")


if __name__ == "__main__":
    unittest.main()
