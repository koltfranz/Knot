from __future__ import annotations

import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from knot.cli.main import main
from knot.core.loader import load_book
from knot.core.scaffold import (
    ROOTS_TO_OPEN,
    SAMPLE_HEADER,
    ScaffoldOptions,
    create_ledger,
)
from knot.core.width import str_width


def uncommented_sample(directory: Path) -> str:
    """把年份文件里的示例段还原为可执行内容（供测试校验示例确实合法）。"""
    lines = (directory / "2026.knot").read_text(encoding="utf-8").splitlines()
    header = lines.index(SAMPLE_HEADER)
    live = lines[:header]
    sample = []
    for line in lines[header + 1 :]:
        if line.startswith(";; "):
            continue
        if line.startswith("; "):
            sample.append(line[2:])
        elif line == ";":
            sample.append("")
    prefix = ['option "operating_currency" "CNY"', 'option "strict" "警告"', ""]
    return "\n".join([*prefix, *live, *sample]) + "\n"


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
            year_text = (directory / "2026.knot").read_text(encoding="utf-8")
            self.assertIn("open", year_text)
            self.assertIn("; 2026-01-01 recur", year_text)
            self.assertIn("budget monthly", year_text)

            _result, _book, diags = load_book(directory / "main.knot")
            self.assertEqual([d for d in diags if d.level == "error"], [])

    def test_accounts_aligned(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            create_ledger(ScaffoldOptions(directory=directory, year=2026))
            lines = (directory / "2026.knot").read_text(encoding="utf-8").splitlines()
            openings = [
                line
                for line in lines
                if not line.lstrip().startswith(";") and "开立" in line and "CNY" in line
            ]
            self.assertEqual(len(openings), len(ROOTS_TO_OPEN))
            columns = {str_width(line[: line.index("CNY")]) for line in openings}
            self.assertEqual(len(columns), 1)

    def test_sample_block_present(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            create_ledger(ScaffoldOptions(directory=directory, year=2026))
            text = (directory / "2026.knot").read_text(encoding="utf-8")
            self.assertIn(SAMPLE_HEADER, text)
            self.assertIn('; 2026-01-11 * "超市"', text)
            self.assertIn('; 2026-01-01 定期 "monthly" "房租"', text)
            self.assertIn("; 2026-01-01 预算 每月 费用:餐饮", text)
            self.assertIn(";; 余额断言", text)

    def test_sample_block_is_valid_when_uncommented(self) -> None:
        """示例段必须是「删掉注释就能跑」的：解注释后校验零错误。"""
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp) / "账本"
            create_ledger(ScaffoldOptions(directory=directory, year=2026))
            ledger = Path(tmp) / "解注释.knot"
            ledger.write_text(uncommented_sample(directory), encoding="utf-8", newline="")

            _result, book, diags = load_book(ledger)
            errors = [d.message for d in diags if d.level == "error"]
            self.assertEqual(errors, [])
            self.assertGreater(len(book.transactions), 5)


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
        self.assertIn("示例账本", output)
        self.assertIn("退出", output)


if __name__ == "__main__":
    unittest.main()
