from __future__ import annotations

import unittest

from knot.core.lexer import (
    is_account,
    is_currency,
    is_date,
    is_flag,
    is_number,
    lex_line,
)


class LexerTest(unittest.TestCase):
    def test_hanzi_account_tokens(self) -> None:
        tokens, diags = lex_line(
            '2026-01-06 "早餐 豆浆油条"    费用:餐饮:早餐    8.50 CNY  @ 资产:现金', 1
        )
        self.assertEqual(diags, [])
        kinds = [t.kind for t in tokens]
        self.assertEqual(kinds[0], "word")
        self.assertEqual(tokens[0].text, "2026-01-06")
        self.assertEqual(tokens[1].kind, "string")
        self.assertEqual(tokens[1].text, "早餐 豆浆油条")
        accounts = [t.text for t in tokens if t.kind == "word" and is_account(t.text)]
        self.assertEqual(accounts, ["2026-01-06", "费用:餐饮:早餐", "CNY", "资产:现金"])

    def test_line_and_column(self) -> None:
        tokens, _ = lex_line("资产:现金     1,000.00 CNY", 42)
        self.assertEqual(tokens[0].line, 42)
        self.assertEqual(tokens[0].col, 1)
        self.assertEqual(tokens[1].col, 11)

    def test_tags_links_and_meta(self) -> None:
        tokens, _ = lex_line('2026-01-10 * "团建" #工作聚餐 ^proj-1', 3)
        self.assertEqual([t.text for t in tokens if t.kind == "tag"], ["工作聚餐"])
        self.assertEqual([t.text for t in tokens if t.kind == "link"], ["proj-1"])
        tokens, _ = lex_line("  ; 凭证: ./凭证/1.jpg", 4)
        self.assertEqual(tokens[0].kind, "comment")

    def test_cost_marks(self) -> None:
        tokens, _ = lex_line("资产:投资:沪深300  1000 FUND {3.8500 CNY}", 1)
        kinds = [t.kind for t in tokens]
        self.assertIn("lbrace", kinds)
        self.assertIn("rbrace", kinds)
        tokens, _ = lex_line("资产:投资:沪深300  1000 FUND @@ 4100.00 CNY", 1)
        self.assertIn("atat", [t.kind for t in tokens])

    def test_unclosed_string(self) -> None:
        _tokens, diags = lex_line('2026-01-01 "未闭合', 7)
        self.assertEqual(len(diags), 1)
        self.assertEqual(diags[0].level, "error")
        self.assertEqual(diags[0].line, 7)

    def test_classifiers(self) -> None:
        self.assertTrue(is_date("2026-01-01"))
        self.assertFalse(is_date("2026-1-1"))
        self.assertTrue(is_flag("P"))
        self.assertFalse(is_flag("x"))
        self.assertTrue(is_number("-1,234.56"))
        self.assertFalse(is_number("1.2.3"))
        self.assertTrue(is_currency("CNY"))
        self.assertTrue(is_currency("FUND"))
        self.assertFalse(is_currency("cny"))
        self.assertTrue(is_account("资产:银行:招行"))
        self.assertFalse(is_account("资产 银行"))


if __name__ == "__main__":
    unittest.main()
