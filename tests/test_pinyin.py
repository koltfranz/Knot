from __future__ import annotations

import unittest

from knot.core.pinyin import initials_of, is_ascii_query, match, pinyin_of


class PinyinTest(unittest.TestCase):
    def test_basic(self) -> None:
        self.assertEqual(pinyin_of("现金"), "xianjin")
        self.assertEqual(pinyin_of("资产:银行"), "zichan:yinhang")
        self.assertEqual(pinyin_of("招行"), "zhaohang")

    def test_initials(self) -> None:
        self.assertEqual(initials_of("资产:银行"), "zc:yh")
        self.assertEqual(initials_of("费用:餐饮:外卖"), "fy:cy:wm")

    def test_ascii_query(self) -> None:
        self.assertTrue(is_ascii_query("xianjin"))
        self.assertTrue(is_ascii_query("zc"))
        self.assertFalse(is_ascii_query("现金"))
        self.assertFalse(is_ascii_query(""))

    def test_match_full_and_initial(self) -> None:
        candidates = ["资产:现金", "资产:银行:招行", "费用:餐饮:外卖", "收入:工资"]
        self.assertEqual(match("xianjin", candidates), ["资产:现金"])
        self.assertEqual(match("zhaohang", candidates), ["资产:银行:招行"])
        self.assertEqual(match("wm", candidates), ["费用:餐饮:外卖"])
        self.assertEqual(match("xi", candidates), ["资产:现金"])
        self.assertEqual(match("gongzi", candidates), ["收入:工资"])

    def test_no_match(self) -> None:
        self.assertEqual(match("zzz", ["资产:现金"]), [])
        self.assertEqual(match("现金", ["资产:现金"]), [])

    def test_unknown_char_ignored(self) -> None:
        self.assertEqual(pinyin_of("现金🪙"), "xianjin")


if __name__ == "__main__":
    unittest.main()
