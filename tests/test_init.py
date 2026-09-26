from __future__ import annotations

import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from knot.cli.main import main
from knot.core.loader import load_book
from knot.core.scaffold import ROOTS_TO_OPEN, ScaffoldOptions, create_ledger
from knot.core.width import str_width


class ScaffoldTest(unittest.TestCase):
    def test_generated_ledger_is_valid(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp) / "我的账本"
            result = create_ledger(ScaffoldOptions(directory=directory, year=2026))
            self.assertEqual(len(result.created), 5)
            self.assertEqual(result.skipped, [])

            _result, _book, diags = load_book(directory / "main.knot")
            self.assertEqual([d for d in diags if d.level == "error"], [])

    def test_second_run_skips(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            create_ledger(ScaffoldOptions(directory=directory, year=2026))
            second = create_ledger(ScaffoldOptions(directory=directory, year=2026))
            self.assertEqual(second.created, [])
            self.assertEqual(len(second.skipped), 5)

    def test_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            create_ledger(ScaffoldOptions(directory=directory, year=2026))
            main_knot = directory / "main.knot"
            main_knot.write_text("; 改坏了\n", encoding="utf-8")
            create_ledger(ScaffoldOptions(directory=directory, year=2026, overwrite=True))
            self.assertIn("结绳 Knot 账本", main_knot.read_text(encoding="utf-8"))

    def test_english_keywords(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            create_ledger(ScaffoldOptions(directory=directory, year=2026, language="en"))
            text = (directory / "main.knot").read_text(encoding="utf-8")
            self.assertIn("option", text)
            self.assertIn("include", text)
            self.assertIn("open", (directory / "2026.knot").read_text(encoding="utf-8"))

            _result, _book, diags = load_book(directory / "main.knot")
            self.assertEqual([d for d in diags if d.level == "error"], [])

    def test_accounts_aligned(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            create_ledger(ScaffoldOptions(directory=directory, year=2026))
            lines = (directory / "2026.knot").read_text(encoding="utf-8").splitlines()
            openings = [line for line in lines if "开立" in line and "CNY" in line]
            self.assertEqual(len(openings), len(ROOTS_TO_OPEN))
            columns = {str_width(line[: line.index("CNY")]) for line in openings}
            self.assertEqual(len(columns), 1)


class InitCommandTest(unittest.TestCase):
    def _run(self, *argv: str) -> tuple[int, str]:
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = main(list(argv))
        return code, buffer.getvalue()

    def test_init_non_interactive(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp) / "账本"
            code, output = self._run("初始化", str(directory), "--非交互", "--年份", "2026")
            self.assertEqual(code, 0)
            self.assertTrue((directory / "main.knot").exists())
            self.assertIn("账本就绪", output)

            code, output = self._run(
                "--账本",
                str(directory / "main.knot"),
                "记",
                "38",
                "餐饮",
                "-f",
                "现金",
                "-d",
                "2026-09-01",
            )
            self.assertEqual(code, 0)

            code, _output = self._run("--账本", str(directory / "main.knot"), "检查", "--静默")
            self.assertEqual(code, 0)

    def test_init_english(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            code, _output = self._run("初始化", tmp, "--非交互", "--语言", "en", "--年份", "2026")
            self.assertEqual(code, 0)
            text = (Path(tmp) / "main.knot").read_text(encoding="utf-8")
            self.assertIn('option "', text)

    def test_init_bad_language(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            code, _output = self._run("初始化", tmp, "--非交互", "--语言", "法语")
            self.assertEqual(code, 2)

    def test_menu_without_tty_prints_choices(self) -> None:
        code, output = self._run("菜单")
        self.assertEqual(code, 0)
        self.assertIn("记一笔", output)
        self.assertIn("退出", output)


if __name__ == "__main__":
    unittest.main()
