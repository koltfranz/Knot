from __future__ import annotations

import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from knot.cli.main import main

BROKEN = """2026-01-01 * "不平衡"
  费用:餐饮     10.00 CNY
  资产:现金     -8.00 CNY
"""


class CreateCommandTest(unittest.TestCase):
    def _run(self, *argv: str) -> tuple[int, str]:
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = main(list(argv))
        return code, buffer.getvalue()

    def test_create_named_ledger(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp) / "我的账本"
            code, output = self._run("create", str(directory), "--非交互", "--年份", "2026")
            self.assertEqual(code, 0)
            self.assertTrue((directory / "main.knot").exists())
            self.assertTrue((directory / "2026.knot").exists())
            self.assertIn("knot open", output)
            code, _output = self._run("--账本", str(directory / "main.knot"), "检查", "--静默")
            self.assertEqual(code, 0)

    def test_create_strips_knot_suffix(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "我的账本.knot"
            code, output = self._run("create", str(target), "--非交互")
            self.assertEqual(code, 0)
            self.assertTrue((Path(tmp) / "我的账本" / "main.knot").exists())
            self.assertIn("账本目录", output)

    def test_create_rejects_bad_language(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            code, _output = self._run(
                "create", str(Path(tmp) / "账本"), "--非交互", "--语言", "法语"
            )
            self.assertEqual(code, 2)

    def test_create_twice_skips(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp) / "账本"
            self._run("create", str(directory), "--非交互")
            code, output = self._run("create", str(directory), "--非交互")
            self.assertEqual(code, 0)
            self.assertIn("已存在，跳过", output)


class OpenCommandTest(unittest.TestCase):
    def _run(self, *argv: str) -> tuple[int, str]:
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = main(list(argv))
        return code, buffer.getvalue()

    def _ledger(self, tmp: str) -> Path:
        directory = Path(tmp) / "小账本"
        with redirect_stdout(io.StringIO()):
            main(["create", str(directory), "--非交互", "--年份", "2026"])
        return directory

    def test_open_missing_suggests_create(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            code, _output = self._run("open", str(Path(tmp) / "不存在"))
            self.assertEqual(code, 2)

    def test_open_without_name_requires_ledger(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cwd = Path.cwd()
            try:
                import os

                os.chdir(tmp)
                code, _output = self._run("open")
                self.assertEqual(code, 2)
            finally:
                os.chdir(cwd)

    def test_open_non_tty_prints_overview(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = self._ledger(tmp)
            code, output = self._run("open", str(directory))
            self.assertEqual(code, 0)
            self.assertIn("交易数：", output)
            self.assertIn("不是交互式终端", output)

    def test_open_accepts_file_and_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = self._ledger(tmp)
            self.assertEqual(self._run("open", str(directory))[0], 0)
            self.assertEqual(self._run("open", str(directory / "main.knot"))[0], 0)

    def test_open_directory_without_main_knot(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            empty = Path(tmp) / "空目录"
            empty.mkdir()
            code, _output = self._run("open", str(empty))
            self.assertEqual(code, 2)

    def test_open_broken_ledger_returns_1(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "坏.knot"
            path.write_text(BROKEN, encoding="utf-8", newline="")
            code, _output = self._run("open", str(path))
            self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main()
