from __future__ import annotations

import unittest
from datetime import date

from knot.core.model import (
    Balance,
    Budget,
    Close,
    Commodity,
    Event,
    Flag,
    Open,
    Price,
    Recur,
    Transaction,
)
from knot.core.parser import Parser

SAMPLE = """option "operating_currency" "CNY"

2026-01-01 open 资产:现金     CNY
2026-01-01 open 权益:期初

2026-01-10 * "团建 AA" #工作聚餐 ^proj-2026Q1
  ; 凭证: ./凭证/2026-01-10-团建.jpg
  费用:餐饮:聚餐      180.00 CNY  @ 资产:现金

2026-01-11 * "超市"
  费用:餐饮:食材     128.00 CNY
  费用:日用品         45.00 CNY
  资产:现金                -173.00 CNY

2026-02-01 balance 资产:现金 1,000.00 CNY
2026-01-01 budget monthly 费用:餐饮 2000.00 CNY
2026-01-01 event "生日" "妈妈"
2026-06-01 price FUND 4.1200 CNY
2026-01-01 commodity FUND
2026-12-31 close 权益:期初
2026-01-01 recur "monthly" "房租" from 2026-01-01 to 2026-03-01
  费用:居住:房租   3,500.00 CNY  @ 资产:银行:招行
"""


class ParserTest(unittest.TestCase):
    def _parse(self, text: str):
        return Parser(text, "test.knot").parse()

    def test_sample_has_no_errors(self) -> None:
        _directives, diags = self._parse(SAMPLE)
        self.assertEqual([d for d in diags if d.level == "error"], [])

    def test_directive_kinds(self) -> None:
        directives, _diags = self._parse(SAMPLE)
        kinds = {type(d) for d in directives}
        for expected in (Open, Balance, Budget, Event, Price, Commodity, Close, Recur, Transaction):
            self.assertIn(expected, kinds)

    def test_transaction_fields(self) -> None:
        directives, _diags = self._parse(SAMPLE)
        tx = next(d for d in directives if isinstance(d, Transaction) and d.narration == "团建 AA")
        self.assertEqual(tx.date, date(2026, 1, 10))
        self.assertEqual(tx.flag, Flag.OK)
        self.assertIsNone(tx.payee)
        self.assertEqual(tx.tags, frozenset({"工作聚餐"}))
        self.assertEqual(tx.links, frozenset({"proj-2026Q1"}))
        self.assertEqual(tx.postings[0].account, "费用:餐饮:聚餐")
        self.assertEqual(tx.postings[0].counterparty, "资产:现金")
        self.assertEqual(tx.meta["凭证"], "./凭证/2026-01-10-团建.jpg")
        self.assertEqual(tx.src_line_start, 6)
        self.assertEqual(tx.src_line_end, 8)

    def test_two_strings_payee_and_narration(self) -> None:
        directives, _ = self._parse(
            '2026-01-05 * "腾讯" "1月工资"\n  收入:工资 -18,000.00 CNY\n  资产:银行:招行\n'
        )
        tx = next(d for d in directives if isinstance(d, Transaction))
        self.assertEqual(tx.payee, "腾讯")
        self.assertEqual(tx.narration, "1月工资")

    def test_blank_leg_is_kept_empty(self) -> None:
        directives, _ = self._parse(
            '2026-01-12 * "饭钱"\n  费用:餐饮:聚餐      88.00 CNY\n  资产:现金\n'
        )
        tx = next(d for d in directives if isinstance(d, Transaction))
        self.assertIsNone(tx.postings[1].units)

    def test_cost_forms(self) -> None:
        directives, _ = self._parse(
            '2026-03-01 * "买入"\n'
            "  资产:投资:沪深300    1000 FUND {3.8500 CNY}\n"
            "  资产:投资:沪深300    1000 FUND @ 4.10 CNY\n"
            "  资产:投资:沪深300    1000 FUND @@ 4100.00 CNY\n"
            "  资产:银行:招行      -3,850.00 CNY\n"
        )
        tx = next(d for d in directives if isinstance(d, Transaction))
        self.assertEqual(tx.postings[0].cost.kind, "unit")
        self.assertEqual(str(tx.postings[0].cost.number), "3.8500")
        self.assertEqual(tx.postings[1].cost.kind, "price")
        self.assertEqual(tx.postings[2].cost.kind, "total")

    def test_panic_recovery(self) -> None:
        text = (
            '2026-13-45 * "非法日期"\n'
            "\n"
            "这不是指令\n"
            "\n"
            '2026-01-02 "正常"    费用:餐饮    10.00 CNY  @ 资产:现金\n'
        )
        directives, diags = self._parse(text)
        errors = [d for d in diags if d.level == "error"]
        self.assertGreaterEqual(len(errors), 1)
        transactions = [d for d in directives if isinstance(d, Transaction)]
        self.assertEqual(len(transactions), 1)
        self.assertEqual(transactions[0].narration, "正常")

    def test_illegal_date_reported(self) -> None:
        _directives, diags = self._parse(
            '2026-13-45 * "非法日期"\n\n2026-01-02 "ok" 费用:餐饮 1.00 CNY @ 资产:现金\n'
        )
        self.assertTrue(any("非法日期" in d.message for d in diags if d.level == "error"))

    def test_unknown_keyword_suggestion(self) -> None:
        _directives, diags = self._parse("2026-01-01 balanc 资产:现金 1.00 CNY\n")
        errors = [d for d in diags if d.level == "error"]
        self.assertEqual(len(errors), 1)
        self.assertIn("balance", errors[0].suggestion or "")

    def test_metadata_on_posting(self) -> None:
        directives, _ = self._parse(
            '2026-01-01 "x"\n  费用:餐饮  10.00 CNY  @ 资产:现金\n  ; 备注: 测试\n'
        )
        tx = next(d for d in directives if isinstance(d, Transaction))
        self.assertEqual(tx.postings[0].meta["备注"], "测试")

    def test_missing_postings_is_error(self) -> None:
        _directives, diags = self._parse(
            '2026-01-01 * "空交易"\n\n2026-01-02 "x" 费用:餐饮 1.00 CNY @ 资产:现金\n'
        )
        self.assertTrue(any(d.level == "error" and "分录" in d.message for d in diags))


if __name__ == "__main__":
    unittest.main()
