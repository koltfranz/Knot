from __future__ import annotations

import unittest
from decimal import Decimal

from knot.core.book import build
from knot.core.keywords import (
    canonical_directive,
    canonical_option_key,
    canonical_option_value,
    canonical_period,
    detect_language,
    directive_spelling,
    option_key_spelling,
    period_spelling,
    write_language,
)
from knot.core.loader import load_book
from knot.core.model import Options
from knot.core.parser import Parser

EN_LEDGER = """option "operating_currency" "CNY"
option "strict" "off"

2026-01-01 open 资产:现金 CNY
2026-01-01 open 权益:期初

2026-01-01 * "期初"
  资产:现金     1,000.00 CNY
  权益:期初

2026-01-01 recur "monthly" "房租" from 2026-01-01 to 2026-03-01
  费用:居住:房租   300.00 CNY  @ 资产:现金

2026-03-31 balance 资产:现金 100.00 CNY
2026-01-01 budget monthly 费用:餐饮 2000.00 CNY
2026-01-01 event "生日" "妈妈"
2026-06-01 price FUND 4.1200 CNY
2026-01-01 commodity FUND
2026-12-31 close 权益:期初
"""

ZH_LEDGER = """选项 "记账币种" "CNY"
选项 "严格度" "关闭"

2026-01-01 开立 资产:现金 CNY
2026-01-01 开立 权益:期初

2026-01-01 * "期初"
  资产:现金     1,000.00 CNY
  权益:期初

2026-01-01 定期 "每月" "房租" 起 2026-01-01 止 2026-03-01
  费用:居住:房租   300.00 CNY  @ 资产:现金

2026-03-31 断言 资产:现金 100.00 CNY
2026-01-01 预算 monthly 费用:餐饮 2000.00 CNY
2026-01-01 事件 "生日" "妈妈"
2026-06-01 报价 FUND 4.1200 CNY
2026-01-01 商品 FUND
2026-12-31 关闭 权益:期初
"""


def build_from(text: str):
    directives, diags = Parser(text, "test.knot").parse()
    book, book_diags = build(directives, Options(strict="off"), {"test.knot": text.splitlines()})
    return book, diags + book_diags


class KeywordsTest(unittest.TestCase):
    def test_directive_mapping(self) -> None:
        self.assertEqual(canonical_directive("open"), "open")
        self.assertEqual(canonical_directive("开立"), "open")
        self.assertIsNone(canonical_directive("不存在的指令"))
        self.assertEqual(directive_spelling("open", "zh"), "开立")
        self.assertEqual(directive_spelling("open", "en"), "open")

    def test_option_keys_and_values(self) -> None:
        self.assertEqual(canonical_option_key("记账币种"), "operating_currency")
        self.assertEqual(canonical_option_key("strict"), "strict")
        self.assertEqual(canonical_option_value("strict", "严格"), "on")
        self.assertEqual(canonical_option_value("严格度", "警告"), "warn")
        self.assertEqual(canonical_option_value("keyword_language", "英文"), "en")
        self.assertEqual(option_key_spelling("strict", "zh"), "严格度")

    def test_periods(self) -> None:
        self.assertEqual(canonical_period("monthly"), "monthly")
        self.assertEqual(canonical_period("每月"), "monthly")
        self.assertIsNone(canonical_period("每两周"))
        self.assertEqual(period_spelling("monthly", "zh"), "每月")

    def test_detect_language(self) -> None:
        self.assertEqual(detect_language(EN_LEDGER.splitlines()), "en")
        self.assertEqual(detect_language(ZH_LEDGER.splitlines()), "zh")
        self.assertEqual(detect_language([]), "zh")
        self.assertEqual(detect_language(['2026-01-01 * "午饭"', "  费用:餐饮 38.00 CNY"]), "zh")

    def test_write_language(self) -> None:
        self.assertEqual(write_language("auto", "en"), "en")
        self.assertEqual(write_language("auto", None), "zh")
        self.assertEqual(write_language("zh", "en"), "zh")
        self.assertEqual(write_language("en", "zh"), "en")

    def test_english_ledger_parses(self) -> None:
        _book, diags = build_from(EN_LEDGER)
        self.assertEqual([d for d in diags if d.level == "error"], [])

    def test_chinese_ledger_parses(self) -> None:
        _book, diags = build_from(ZH_LEDGER)
        self.assertEqual([d for d in diags if d.level == "error"], [])

    def test_bilingual_equivalence(self) -> None:
        en_book, en_diags = build_from(EN_LEDGER)
        zh_book, zh_diags = build_from(ZH_LEDGER)
        self.assertEqual(en_book.summary(), zh_book.summary())
        self.assertEqual(
            [(t.date, str(t.postings[0].units.number), t.narration) for t in en_book.transactions],
            [(t.date, str(t.postings[0].units.number), t.narration) for t in zh_book.transactions],
        )
        self.assertEqual(_levels(en_diags), _levels(zh_diags))
        self.assertEqual(en_book.transactions[-1].meta.get("定期"), "monthly")

    def test_chinese_options_canonicalized(self) -> None:
        options = Options.from_pairs({"记账币种": "CNY", "严格度": "严格", "关键字语言": "英文"})
        self.assertEqual(options.operating_currency, "CNY")
        self.assertEqual(options.strict, "on")
        self.assertEqual(options.keyword_language, "en")

    def test_diagnostic_in_english_ledger(self) -> None:
        _book, diags = build_from("2026-01-01 openn 资产:现金 CNY\n")
        errors = [d for d in diags if d.level == "error"]
        self.assertTrue(errors)
        self.assertIn("open", errors[0].message + (errors[0].suggestion or ""))

    def test_recur_expansion_identical(self) -> None:
        en_book, _ = build_from(EN_LEDGER)
        zh_book, _ = build_from(ZH_LEDGER)
        en_rent = en_book.balance_of("费用:居住:房租")["CNY"]
        zh_rent = zh_book.balance_of("费用:居住:房租")["CNY"]
        self.assertEqual(en_rent, Decimal("900.00"))
        self.assertEqual(en_rent, zh_rent)

    def test_loader_records_languages(self) -> None:
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "main.knot"
            path.write_text(ZH_LEDGER, encoding="utf-8")
            result = load_book(path)[0]
            self.assertEqual(result.languages[str(path)], "zh")

            path.write_text(EN_LEDGER, encoding="utf-8")
            result = load_book(path)[0]
            self.assertEqual(result.languages[str(path)], "en")

    def test_syntax_reference_matches_code(self) -> None:
        """docs/语法大全.md 的对照表必须与 core/keywords.py 一致。"""
        import importlib.util
        from pathlib import Path

        root = Path(__file__).resolve().parents[1]
        spec = importlib.util.spec_from_file_location(
            "生成语法大全", root / "scripts" / "生成语法大全.py"
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        doc = (root / "docs" / "语法大全.md").read_text(encoding="utf-8")
        self.assertEqual(doc, module.apply_to_document(doc, module.render_tables()))


def _levels(diags) -> list[tuple[str, int, str]]:
    return [(d.level, d.line, d.message) for d in diags]


if __name__ == "__main__":
    unittest.main()
