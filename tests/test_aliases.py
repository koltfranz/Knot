from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from knot.core.aliases import AliasTable, load_alias_file


class AliasTest(unittest.TestCase):
    def test_layers(self) -> None:
        table = AliasTable()
        self.assertEqual(table.resolve("招行").target, "资产:银行:招行")
        self.assertEqual(table.resolve("A").target, "资产")
        self.assertEqual(table.resolve("X:交通").target, "费用:交通")
        self.assertEqual(table.resolve("资产:现金").target, "资产:现金")
        self.assertEqual(table.resolve("支出").target, "费用")

    def test_user_overrides_builtin(self) -> None:
        table = AliasTable({"餐饮": "费用:餐饮:外卖"})
        self.assertEqual(table.resolve("餐饮").target, "费用:餐饮:外卖")

    def test_multiple_candidates(self) -> None:
        table = AliasTable()
        resolution = table.resolve("餐")
        self.assertIsNone(resolution.target)
        self.assertIn("费用:餐饮", resolution.candidates)
        self.assertGreater(len(resolution.candidates), 1)

    def test_unknown(self) -> None:
        table = AliasTable()
        resolution = table.resolve("不存在的东西")
        self.assertIsNone(resolution.target)
        self.assertEqual(resolution.candidates, [])

    def test_load_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "别名.knot"
            path.write_text(
                "; 注释\n咖啡 = 费用:餐饮:咖啡\n\n星巴克=费用:餐饮:咖啡\n", encoding="utf-8"
            )
            mapping = load_alias_file(path)
        self.assertEqual(mapping, {"咖啡": "费用:餐饮:咖啡", "星巴克": "费用:餐饮:咖啡"})


if __name__ == "__main__":
    unittest.main()
