from __future__ import annotations

import unittest
from datetime import date, timedelta

from knot.core.date_cn import parse_date, parse_month

TODAY = date(2026, 9, 25)


class DateCnTest(unittest.TestCase):
    def test_relative(self) -> None:
        self.assertEqual(parse_date("今天", TODAY), TODAY)
        self.assertEqual(parse_date("今日", TODAY), TODAY)
        self.assertEqual(parse_date("today", TODAY), TODAY)
        self.assertEqual(parse_date("昨天", TODAY), date(2026, 9, 24))
        self.assertEqual(parse_date("昨日", TODAY), date(2026, 9, 24))
        self.assertEqual(parse_date("前天", TODAY), date(2026, 9, 23))
        self.assertEqual(parse_date("明天", TODAY), date(2026, 9, 26))

    def test_absolute(self) -> None:
        self.assertEqual(parse_date("2026-09-20"), date(2026, 9, 20))
        self.assertEqual(parse_date("2026/9/20"), date(2026, 9, 20))
        self.assertEqual(parse_date("2026年9月20日"), date(2026, 9, 20))
        self.assertEqual(parse_date("9月20日", TODAY), date(2026, 9, 20))
        self.assertEqual(parse_date("9月20号", TODAY), date(2026, 9, 20))
        self.assertEqual(parse_date("9/20", TODAY), date(2026, 9, 20))
        self.assertEqual(parse_date("9-20", TODAY), date(2026, 9, 20))

    def test_last_week(self) -> None:
        monday = TODAY - timedelta(days=TODAY.isoweekday() - 1) - timedelta(days=7)
        self.assertEqual(parse_date("上周一", TODAY), monday)
        self.assertEqual(parse_date("上周五", TODAY), monday + timedelta(days=4))

    def test_month_range(self) -> None:
        self.assertEqual(parse_month("本月", TODAY), (date(2026, 9, 1), date(2026, 9, 30)))
        self.assertEqual(parse_month("上月", TODAY), (date(2026, 8, 1), date(2026, 8, 31)))
        self.assertEqual(parse_month("今年", TODAY), (date(2026, 1, 1), date(2026, 12, 31)))
        self.assertEqual(parse_month("2026-09", TODAY), (date(2026, 9, 1), date(2026, 9, 30)))
        self.assertEqual(parse_month("2026年2月", TODAY), (date(2026, 2, 1), date(2026, 2, 28)))

    def test_errors(self) -> None:
        with self.assertRaises(ValueError):
            parse_date("下个季度", TODAY)
        with self.assertRaises(ValueError):
            parse_month("2026年13月", TODAY)


if __name__ == "__main__":
    unittest.main()
