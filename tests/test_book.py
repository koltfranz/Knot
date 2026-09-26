from __future__ import annotations

import unittest
from datetime import date
from decimal import Decimal

from knot.core.book import build
from knot.core.model import Options
from knot.core.parser import Parser


def build_from(text: str, strict: str = "off"):
    parser = Parser(text, "test.knot")
    directives, diags = parser.parse()
    book, book_diags = build(directives, Options(strict=strict), {"test.knot": text.splitlines()})
    return book, diags + book_diags


def errors(diags) -> list:
    return [d for d in diags if d.level == "error"]


def warnings(diags) -> list:
    return [d for d in diags if d.level == "warning"]


class BookTest(unittest.TestCase):
    def test_single_leg_generates_counterparty(self) -> None:
        book, diags = build_from('2026-01-01 "午饭"  费用:餐饮  38.00 CNY  @ 资产:现金\n')
        self.assertEqual(errors(diags), [])
        tx = book.transactions[0]
        self.assertEqual(len(tx.postings), 2)
        generated = tx.postings[1]
        self.assertTrue(generated.generated)
        self.assertEqual(generated.account, "资产:现金")
        self.assertEqual(generated.units.number, Decimal("-38.00"))

    def test_single_leg_uses_default_counterparty(self) -> None:
        book, diags = build_from('2026-01-01 "买菜"  费用:餐饮  62.30 CNY\n')
        self.assertEqual(errors(diags), [])
        self.assertEqual(book.transactions[0].postings[1].account, "资产:现金")

    def test_single_leg_without_counterparty_is_error(self) -> None:
        _book, diags = build_from('2026-01-01 "转账"  资产:现金  100.00 CNY\n')
        self.assertTrue(any("对手科目" in d.message for d in errors(diags)))

    def test_auto_balance_blank_leg(self) -> None:
        book, diags = build_from(
            '2026-01-12 * "饭钱"\n  费用:餐饮:聚餐      88.00 CNY\n  资产:现金\n'
        )
        self.assertEqual(errors(diags), [])
        self.assertEqual(book.transactions[0].postings[1].units.number, Decimal("-88.00"))

    def test_two_blank_legs_is_error(self) -> None:
        _book, diags = build_from('2026-01-03 * "缺金额"\n  费用:餐饮\n  资产:现金\n')
        self.assertTrue(any("留空" in d.message for d in errors(diags)))

    def test_unbalanced_is_error(self) -> None:
        _book, diags = build_from(
            '2026-01-04 * "不平衡"\n  费用:餐饮  10.00 CNY\n  资产:现金  -8.00 CNY\n'
        )
        self.assertTrue(any("借贷不平衡" in d.message for d in errors(diags)))

    def test_balance_assertion(self) -> None:
        good = (
            "2026-01-01 open 资产:现金 CNY\n"
            '2026-01-01 * "期初"\n  资产:现金  1,000.00 CNY\n  权益:期初\n'
            "2026-02-01 balance 资产:现金 1,000.00 CNY\n"
        )
        _book, diags = build_from(good)
        self.assertEqual(errors(diags), [])

        bad = good.replace("1,000.00 CNY\n", "900.00 CNY\n", 1)
        _book, diags = build_from(bad)
        self.assertTrue(any("余额断言失败" in d.message for d in errors(diags)))

    def test_identity_check(self) -> None:
        _book, diags = build_from(
            '2026-01-04 * "不平衡"\n  费用:餐饮  10.00 CNY\n  资产:现金  -8.00 CNY\n'
        )
        self.assertTrue(any("会计恒等式" in d.message for d in errors(diags)))

    def test_recur_expansion(self) -> None:
        book, diags = build_from(
            "2026-01-01 open 费用:居住:房租\n"
            "2026-01-01 open 资产:银行:招行 CNY\n"
            '2026-01-01 * "期初"\n  资产:银行:招行  50,000.00 CNY\n  权益:期初\n'
            '2026-01-01 recur "monthly" "房租" from 2026-01-01 to 2026-04-01\n'
            "  费用:居住:房租   3,500.00 CNY  @ 资产:银行:招行\n"
        )
        self.assertEqual(errors(diags), [])
        self.assertEqual(len(book.transactions), 5)
        self.assertEqual(book.balance_of("资产:银行:招行")["CNY"], Decimal("36000.00"))

    def test_commodity_position_is_not_identity_error(self) -> None:
        book, diags = build_from(
            "2026-03-01 open 资产:投资:沪深300 FUND\n"
            "2026-03-01 open 资产:银行:招行 CNY\n"
            '2026-03-01 * "期初"\n  资产:银行:招行  100,000.00 CNY\n  权益:期初\n'
            '2026-03-02 * "买入"\n'
            "  资产:投资:沪深300     1000 FUND {3.8500 CNY}\n"
            "  资产:银行:招行      -3,850.00 CNY\n"
        )
        self.assertEqual(errors(diags), [])
        self.assertEqual(book.balance_of("资产:投资:沪深300")["FUND"], Decimal("1000.00"))

    def test_strict_modes(self) -> None:
        text = '2026-01-01 "午饭"  费用:餐饮:未知  38.00 CNY  @ 资产:现金\n'
        _book, diags = build_from(text, strict="off")
        self.assertEqual(warnings(diags), [])
        self.assertTrue(any(d.level == "hint" for d in diags))

        _book, diags = build_from(text, strict="warn")
        self.assertTrue(any("未声明科目" in d.message for d in warnings(diags)))

        _book, diags = build_from(text, strict="on")
        self.assertTrue(any("科目未声明" in d.message for d in errors(diags)))

    def test_summary_shape(self) -> None:
        book, _diags = build_from(
            "2026-01-01 open 资产:现金 CNY\n"
            '2026-01-01 * "期初"\n  资产:现金  1,000.00 CNY\n  权益:期初\n'
        )
        summary = book.summary()
        self.assertEqual(summary["交易数"], 1)
        self.assertEqual(summary["科目余额"]["资产:现金 CNY"], "1,000.00")
        self.assertEqual(summary["净资产"]["CNY"], "1,000.00")

    def test_sorting_by_date(self) -> None:
        book, _ = build_from(
            '2026-02-01 "后"  费用:餐饮  1.00 CNY  @ 资产:现金\n'
            '2026-01-01 "前"  费用:餐饮  2.00 CNY  @ 资产:现金\n'
        )
        self.assertEqual(
            [tx.date for tx in book.transactions], [date(2026, 1, 1), date(2026, 2, 1)]
        )


if __name__ == "__main__":
    unittest.main()
