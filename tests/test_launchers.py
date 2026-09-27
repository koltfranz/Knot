from __future__ import annotations

import io
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from knot.cli.commands.serve import should_open_browser
from knot.cli.main import build_parser, main

ROOT = Path(__file__).resolve().parents[1]

LAUNCHERS = {
    "界面.bat": "tui",
    "网页.bat": "serve --open",
    "界面.sh": "tui",
    "网页.sh": "serve --open",
    "界面.ps1": "tui",
    "网页.ps1": "serve --open",
}

FORWARDERS = {".bat": "knot.bat", ".sh": "knot.sh", ".ps1": "knot.ps1"}

BAT_FILES = ["knot.bat", "界面.bat", "网页.bat"]
PS1_FILES = ["knot.ps1", "界面.ps1", "网页.ps1"]


def parse(argv: list[str]):
    return build_parser().parse_args(["--账本", "x.knot", *argv])


class LauncherFileTest(unittest.TestCase):
    def test_launcher_scripts_exist(self) -> None:
        for name, command in LAUNCHERS.items():
            path = ROOT / name
            self.assertTrue(path.exists(), f"缺少启动器：{name}")
            text = path.read_text(encoding="utf-8-sig")
            self.assertIn(FORWARDERS[path.suffix], text, name)
            self.assertIn(command, text, name)

    def test_powershell_launcher_exists(self) -> None:
        text = (ROOT / "knot.ps1").read_text(encoding="utf-8-sig")
        self.assertIn("venv", text)
        self.assertIn("knot", text)
        self.assertIn("menu", text)

    def test_bat_launchers_are_ascii(self) -> None:
        """批处理只使用 ASCII 命令：中文参数会受控制台代码页影响而损坏。"""
        for name in BAT_FILES:
            raw = (ROOT / name).read_bytes()
            code_lines = [
                line
                for line in raw.splitlines()
                if line.strip() and not line.lstrip().lower().startswith((b"rem", b"@"))
            ]
            code = b"\n".join(code_lines).decode("ascii", errors="replace")
            self.assertNotIn("\ufffd", code, f"{name} 的命令行必须为 ASCII")
            self.assertNotRegex(code, r"[\u4e00-\u9fff]", f"{name} 的命令行不应含中文")

    def test_ps1_launchers_use_ascii_commands(self) -> None:
        for name in ("界面.ps1", "网页.ps1"):
            text = (ROOT / name).read_text(encoding="utf-8-sig")
            command_line = next(
                line
                for line in text.splitlines()
                if line.strip().startswith("&") and "knot.ps1" in line
            )
            self.assertNotRegex(command_line, r"[\u4e00-\u9fff]", f"{name} 的命令行不应含中文")

    def test_sh_launchers_use_ascii_commands(self) -> None:
        for name in (n for n in LAUNCHERS if n.endswith(".sh")):
            text = (ROOT / name).read_text(encoding="utf-8")
            command_line = next(line for line in text.splitlines() if line.startswith("exec "))
            self.assertRegex(command_line, r"^exec .* (tui|serve --open)$", name)

    def test_bat_files_use_crlf(self) -> None:
        for name in BAT_FILES:
            raw = (ROOT / name).read_bytes()
            self.assertIn(b"\r\n", raw, f"{name} 必须使用 CRLF 行尾（cmd 解析要求）")
            self.assertNotIn(b"\n\n", raw.replace(b"\r\n", b""), name)

    def test_ps1_files_use_bom_and_crlf(self) -> None:
        for name in PS1_FILES:
            raw = (ROOT / name).read_bytes()
            self.assertTrue(raw.startswith(b"\xef\xbb\xbf"), f"{name} 需要 UTF-8 BOM")
            self.assertIn(b"\r\n", raw, name)
            self.assertNotIn(b"\n", raw.replace(b"\r\n", b""), f"{name} 必须使用 CRLF")

    def test_gitattributes_declares_crlf_types(self) -> None:
        text = (ROOT / ".gitattributes").read_text(encoding="utf-8")
        self.assertIn("*.bat text eol=crlf", text)
        self.assertIn("*.ps1 text eol=crlf", text)


class BrowserOpenTest(unittest.TestCase):
    def test_forced_open(self) -> None:
        self.assertTrue(should_open_browser(parse(["服务", "--打开浏览器"])))

    def test_suppressed(self) -> None:
        self.assertFalse(should_open_browser(parse(["服务", "--不打开浏览器"])))
        self.assertFalse(should_open_browser(parse(["服务", "--打开浏览器", "--不打开浏览器"])))

    def test_default_follows_tty(self) -> None:
        args = parse(["服务"])
        self.assertEqual(should_open_browser(args), __import__("sys").stdin.isatty())

    def test_serve_accepts_ledger_and_port(self) -> None:
        args = parse(["服务", "--端口", "0", "--静默", "--不打开浏览器"])
        self.assertEqual(args.port, 0)
        self.assertTrue(args.quiet)
        self.assertFalse(should_open_browser(args))


class MenuTest(unittest.TestCase):
    def test_menu_lists_tui_and_web(self) -> None:
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = main(["--账本", "x.knot", "菜单"])
        output = buffer.getvalue()
        self.assertEqual(code, 0)
        self.assertIn("浏览器界面", output)
        self.assertIn("终端界面", output)

    def test_menu_actions_dispatch(self) -> None:
        from knot.cli.commands.menu import MENU

        actions = {label: action for _key, label, action in MENU}
        self.assertEqual(actions["浏览器界面（本地服务）"], ["服务", "--打开浏览器"])
        self.assertEqual(actions["终端界面（TUI）"], ["界面"])
        self.assertEqual(actions["示例账本（复制到当前目录）"], ["示例"])
        self.assertEqual(actions["环境自检"], ["自检"])


class CompletionTest(unittest.TestCase):
    def test_powershell_completion(self) -> None:
        from knot.cli.completion import generate

        text = generate("powershell", build_parser())
        self.assertIn("Register-ArgumentCompleter", text)
        self.assertIn("'create'", text)
        self.assertIn("'示例'", text)

        pwsh = generate("pwsh", build_parser())
        self.assertEqual(text, pwsh)


if __name__ == "__main__":
    unittest.main()
