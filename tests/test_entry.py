from __future__ import annotations

import io
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from knot.cli import entry
from knot.cli.commands import launch
from knot.cli.main import main
from knot.core.loader import load_book


class ChooserTest(unittest.TestCase):
    def test_default_when_no_dialog_available(self) -> None:
        with (
            mock.patch.object(entry, "_pick_dialog", return_value=None),
            mock.patch.object(entry.sys, "stdin", io.StringIO()),
        ):
            self.assertEqual(entry.choose(), entry.DEFAULT_CHOICE)

    def test_reads_choice_from_dialog(self) -> None:
        completed = subprocess.CompletedProcess(args=[], returncode=0, stdout="tui\n", stderr="")
        with (
            mock.patch.object(entry, "_pick_dialog", return_value=lambda: ["fake-dialog"]),
            mock.patch.object(entry.subprocess, "run", return_value=completed),
        ):
            self.assertEqual(entry.choose(), "tui")

    def test_timeout_falls_back_to_default(self) -> None:
        with (
            mock.patch.object(entry, "_pick_dialog", return_value=lambda: ["fake-dialog"]),
            mock.patch.object(
                entry.subprocess,
                "run",
                side_effect=subprocess.TimeoutExpired("fake-dialog", 1),
            ),
        ):
            self.assertEqual(entry.choose(timeout=0.01), entry.DEFAULT_CHOICE)

    def test_empty_output_means_quit(self) -> None:
        completed = subprocess.CompletedProcess(args=[], returncode=1, stdout="", stderr="")
        with (
            mock.patch.object(entry, "_pick_dialog", return_value=lambda: ["fake-dialog"]),
            mock.patch.object(entry.subprocess, "run", return_value=completed),
        ):
            self.assertEqual(entry.choose(), "quit")

    def test_windows_dialog_script(self) -> None:
        command = entry._windows_dialog()
        self.assertEqual(command[0], "powershell")
        self.assertIn("-File", command)
        script = Path(command[-1]).read_text(encoding="utf-8-sig")
        self.assertIn("System.Windows.Forms", script)
        for label in entry.LABELS.values():
            self.assertIn(label, script)
        self.assertIn("退出", script)

    def test_linux_dialog_commands(self) -> None:
        zenity = entry._zenity_dialog()
        self.assertIn("--list", zenity)
        self.assertIn(entry.LABELS["browser"], zenity)

        kdialog = entry._kdialog_dialog()
        self.assertIn("--menu", kdialog)
        self.assertIn("browser", kdialog)

    def test_macos_dialog_command(self) -> None:
        command = entry._macos_dialog()
        self.assertEqual(command[0], "osascript")
        self.assertIn(entry.LABELS["demo"], command[2])

    def test_tty_menu(self) -> None:
        with mock.patch("builtins.input", return_value="2"), redirect_stdout(io.StringIO()):
            self.assertEqual(entry._tty_menu(), "tui")
        with mock.patch("builtins.input", return_value=""), redirect_stdout(io.StringIO()):
            self.assertEqual(entry._tty_menu(), "browser")
        with mock.patch("builtins.input", return_value="0"), redirect_stdout(io.StringIO()):
            self.assertEqual(entry._tty_menu(), "quit")

    def test_label_lookup(self) -> None:
        self.assertEqual(entry.BY_LABEL[entry.LABELS["tui"]], "tui")
        self.assertEqual(entry.label_of("unknown"), "unknown")


class SpawnTest(unittest.TestCase):
    def test_spawn_tui_uses_new_console_on_windows(self) -> None:
        with (
            mock.patch.object(entry, "IS_WINDOWS", True),
            mock.patch.object(entry.subprocess, "Popen") as popen,
        ):
            ok = entry.spawn_tui("python.exe", Path("x.knot"))
        self.assertTrue(ok)
        args, kwargs = popen.call_args
        self.assertEqual(args[0][0], "cmd")
        self.assertIn("界面", args[0][2])
        self.assertIn("x.knot", args[0][2])
        self.assertEqual(kwargs["creationflags"], entry.WINDOWS_CREATE_NEW_CONSOLE)

    def test_spawn_browser_uses_terminal_emulator(self) -> None:
        with (
            mock.patch.object(entry, "IS_WINDOWS", False),
            mock.patch.object(entry, "IS_MACOS", False),
            mock.patch.object(entry, "_linux_terminal", return_value=["xterm", "-e"]),
            mock.patch.object(entry.subprocess, "Popen") as popen,
        ):
            self.assertTrue(entry.spawn_browser("python", Path("x.knot")))
        command = popen.call_args[0][0]
        self.assertEqual(command[0], "xterm")
        self.assertIn("服务", command[-1])

    def test_spawn_returns_false_without_terminal(self) -> None:
        with (
            mock.patch.object(entry, "IS_WINDOWS", False),
            mock.patch.object(entry, "IS_MACOS", False),
            mock.patch.object(entry, "_linux_terminal", return_value=None),
        ):
            self.assertFalse(entry.spawn_tui("python", Path("x.knot")))

    def test_macos_spawn_uses_terminal_app(self) -> None:
        with (
            mock.patch.object(entry, "IS_WINDOWS", False),
            mock.patch.object(entry, "IS_MACOS", True),
            mock.patch.object(entry.subprocess, "Popen") as popen,
        ):
            self.assertTrue(entry.spawn_tui("python3", Path("x.knot")))
        self.assertEqual(popen.call_args[0][0][:2], ["open", "-a"])

    def test_windowless_executable(self) -> None:
        result = entry.windowless_executable()
        self.assertTrue(result)
        if entry.IS_WINDOWS:
            self.assertTrue(result.endswith(".exe"))


class LedgerHomeTest(unittest.TestCase):
    def test_explicit_directory(self) -> None:
        self.assertEqual(launch.ledger_home("D:/x/账本"), Path("D:/x/账本"))

    def test_environment_variable(self) -> None:
        with mock.patch.dict("os.environ", {"KNOT_HOME": "D:/env/账本"}):
            self.assertEqual(launch.ledger_home(None), Path("D:/env/账本"))

    def test_default_home(self) -> None:
        with mock.patch.object(entry, "home_from_env", return_value=None):
            self.assertEqual(launch.ledger_home(None), Path.home() / launch.DEFAULT_HOME_NAME)

    def test_ensure_ledger_creates_scaffold(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "结绳账本"
            main_knot = launch.ensure_ledger(home)
            self.assertTrue(main_knot.exists())
            _result, _book, diags = load_book(main_knot)
            self.assertEqual([d for d in diags if d.level == "error"], [])

    def test_ensure_ledger_keeps_existing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            first = launch.ensure_ledger(home)
            first.write_text(first.read_text(encoding="utf-8") + "; 手工改动\n", encoding="utf-8")
            again = launch.ensure_ledger(home)
            self.assertIn("手工改动", again.read_text(encoding="utf-8"))

    def test_ensure_demo_copies_example(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ledger = launch.ensure_demo(Path(tmp))
            self.assertTrue(ledger.exists())
            self.assertEqual(ledger.parent.name, "演示账本")


class LaunchCommandTest(unittest.TestCase):
    def _run(self, *argv: str) -> tuple[int, str]:
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = main(list(argv))
        return code, buffer.getvalue()

    def test_tui_interface_spawns_window(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "账本"
            with mock.patch.object(entry, "spawn_tui", return_value=True) as spawn:
                code, output = self._run("入口", "--界面", "终端", "--账本目录", str(home))
            self.assertEqual(code, 0)
            self.assertIn("已在新窗口打开终端界面", output)
            self.assertTrue(spawn.called)
            self.assertTrue((home / "main.knot").exists())

    def test_demo_interface_opens_browser(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "账本"
            with mock.patch.object(entry, "spawn_browser", return_value=True) as spawn:
                code, output = self._run("入口", "--界面", "示例", "--账本目录", str(home))
            self.assertEqual(code, 0)
            self.assertIn("已在新窗口启动本地服务", output)
            self.assertTrue(spawn.called)
            self.assertTrue((home / "演示账本" / "main.knot").exists())

    def test_quit_from_chooser(self) -> None:
        with mock.patch.object(entry, "choose", return_value="quit"):
            code, _output = self._run("入口")
        self.assertEqual(code, 0)

    def test_chooser_default_opens_browser(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "账本"
            with (
                mock.patch.object(entry, "choose", return_value=entry.DEFAULT_CHOICE),
                mock.patch.object(entry, "spawn_browser", return_value=True) as spawn,
            ):
                code, _output = self._run("入口", "--账本目录", str(home))
            self.assertEqual(code, 0)
            self.assertTrue(spawn.called)
            self.assertTrue((home / "main.knot").exists())


if __name__ == "__main__":
    unittest.main()
